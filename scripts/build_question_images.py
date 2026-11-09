#!/usr/bin/env python3
"""Generate question-only images from the original CEEC exam PDFs.

Run via the GitHub Action in this repository. A PDF's equations/graphics are
preserved by rasterizing the actual PDF, never attempting to retype math.

IMPORTANT: Machine segmentation can be imperfect. The generated review page
must be checked before treating all 260 images as verified.
"""
from __future__ import annotations
import html
import json
import re
import sys
import time
from pathlib import Path

import fitz
import requests
from PIL import Image, ImageOps, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'assets'/'questions'
HTML=(ROOT/'index.html').read_text(encoding='utf-8')
EXAMS=json.loads(re.search(r'const EXAMS\s*=\s*(\[.*?\]);',HTML,re.S).group(1))
NUM_RE=re.compile(r'^\s*(\d{1,2})\s*[.．、](?:\s*|$)')
LETTER_RE=re.compile(r'^\s*([A-G])\s*[.．、](?:\s*|$)')
SHARED_RE=re.compile(r'(?:四|肆)\s*[、\.．]\s*(?:混合題|非選擇題|題組)')
END_RE=re.compile(r'(?:參考公式|附錄|試題結束|【參考)')


def get_pdf(url:str)->bytes:
    s=requests.Session()
    s.headers.update({'User-Agent':'Mozilla/5.0 (compatible; GSAT-Math study materials archiver)','Accept':'application/pdf,*/*'})
    last=None
    for attempt in range(3):
        try:
            r=s.get(url,timeout=60)
            r.raise_for_status()
            if not r.content.startswith(b'%PDF-'):
                raise RuntimeError(f'Expected PDF, received {r.headers.get("Content-Type")} ({len(r.content)} bytes)')
            return r.content
        except Exception as e:
            last=e;time.sleep(attempt+1)
    raise RuntimeError(f'Could not fetch official PDF: {last}')


def lines_on_page(page):
    lines=[]
    data=page.get_text('dict',sort=True)
    for block in data['blocks']:
        if block.get('type')!=0:continue
        for line in block.get('lines',[]):
            spans=line.get('spans',[])
            if not spans:continue
            s=''.join(sp.get('text','') for sp in spans).strip()
            if not s:continue
            x0=min(sp['bbox'][0] for sp in spans)
            y0=min(sp['bbox'][1] for sp in spans)
            lines.append((x0,y0,s))
    return sorted(lines,key=lambda t:(t[1],t[0]))


def locate(doc):
    numbered={n:[] for n in range(1,21)}
    lettered={k:[] for k in 'ABCDEFG'}
    shared=[];ends=[]
    for ip,page in enumerate(doc):
        for x,y,s in lines_on_page(page):
            if not 35<=y<=page.rect.height-43:continue
            # All real exam question numbers start near the left margin.
            if x<145:
                m=NUM_RE.match(s)
                if m:
                    n=int(m.group(1))
                    if 1<=n<=20:numbered[n].append((ip,y,x,s[:45]))
                m=LETTER_RE.match(s)
                if m:lettered[m.group(1)].append((ip,y,x,s[:45]))
            if x<190 and SHARED_RE.search(s):shared.append((ip,y,x,s[:45]))
            if x<195 and END_RE.search(s):ends.append((ip,y,x,s[:45]))
    return numbered,lettered,shared,ends


def abspos(doc,p):
    return sum(doc[i].rect.height for i in range(p[0]))+p[1]


def choose_anchors(doc,e,nums,letters):
    anchors={};prev=-1
    for q in range(1,21):
        candidates=nums[q]
        if e['isOld'] and q>e['singleQuestions'][-1] and q>e['multiQuestions'][-1]:
            letter=chr(ord('A')+q-14)
            candidates=candidates+letters[letter]
        # Prioritize scan order. Use only unique question markers after previous.
        matches=[p for p in candidates if abspos(doc,p)>prev+7]
        if not matches:
            anchors[q]=None;continue
        # Most exam questions have a 55–100 pt left gutter; deprioritize inner numbers.
        pick=min(matches,key=lambda p:(abspos(doc,p),max(p[2]-100,0)*0.05))
        anchors[q]=pick;prev=abspos(doc,pick)
    return anchors


def part_image(page,top,bottom,dpi=150):
    h=page.rect.height; w=page.rect.width
    top=max(45,top);bottom=min(h-43,bottom)
    if bottom-top<16:return None
    # Keep original layout, including diagrams, equations, and answer choices.
    clip=fitz.Rect(53,top,w-43,bottom)
    pix=page.get_pixmap(matrix=fitz.Matrix(dpi/72,dpi/72),clip=clip,alpha=False)
    return Image.frombytes('RGB',(pix.width,pix.height),pix.samples)


def between(doc,start,end):
    if abspos(doc,end)<=abspos(doc,start)+4:return None
    parts=[]
    for page_idx in range(start[0],end[0]+1):
        page=doc[page_idx]
        top=start[1] if page_idx==start[0] else 48
        bottom=end[1] if page_idx==end[0] else page.rect.height-44
        part=part_image(page,top,bottom)
        if part is not None:parts.append(part)
    if not parts:return None
    if len(parts)==1:return parts[0]
    w=max(im.width for im in parts)
    whole=Image.new('RGB',(w,sum(i.height for i in parts)+8*(len(parts)-1)),'white')
    y=0
    for im in parts:
        whole.paste(im,(0,y));y+=im.height+8
    return whole


def save_webp(image,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    # Trim margins only when there is strong near-white border.
    image.save(path,'WEBP',quality=83,method=5)


def build(e):
    outdir=ASSETS/e['id'];outdir.mkdir(parents=True,exist_ok=True)
    pdf=get_pdf(e['paper'])
    doc=fitz.open(stream=pdf,filetype='pdf')
    nums,letters,shared,ends=locate(doc)
    anchors=choose_anchors(doc,e,nums,letters)
    log=[];items={}
    for q in range(1,21):
        start=anchors[q]; nxt=anchors.get(q+1)
        if not start:
            log.append(f'q{q:02}: MISSING question marker');continue
        if nxt and abspos(doc,nxt)<=abspos(doc,start):
            log.append(f'q{q:02}: BAD marker order');continue
        if not nxt:
            if q<20:
                log.append(f'q{q:02}: next question marker missing, cannot delimit safely');continue
            possible=[p for p in ends if abspos(doc,p)>abspos(doc,start)+25]
            nxt=min(possible,key=lambda p:abspos(doc,p)) if possible else (min(len(doc)-1,start[0]+1),45,60,'end')
            if nxt[0]<=start[0]:nxt=(start[0],doc[start[0]].rect.height-43,60,'end')
        # Add generous y padding without overflowing into previous/next question.
        first=(start[0],max(47,start[1]-8),start[2],start[3]); last=(nxt[0],max(48,nxt[1]-11),nxt[2],nxt[3])
        image=between(doc,first,last)
        if image is None or image.height<65:
            log.append(f'q{q:02}: empty image');continue
        name=f'q{q:02}.webp'
        save_webp(image,outdir/name)
        items[str(q)]={'image':f'assets/questions/{e["id"]}/{name}','size':[image.width,image.height], 'start_page':start[0]+1}
        log.append(f'q{q:02}: {image.width}x{image.height} PDF p{start[0]+1} {start[3]}')
    # Some non-choice questions share a figure or longer group stem. Crop once and repeat above each question.
    if not e['isOld'] and anchors.get(18):
        starts=[s for s in shared if abspos(doc,s)<abspos(doc,anchors[18]) and (not anchors.get(17) or abspos(doc,s)>abspos(doc,anchors[17]))]
        if starts:
            pos=min(starts,key=lambda v:abspos(doc,v));intro=between(doc,(pos[0],pos[1]-6,pos[2],pos[3]),(anchors[18][0],anchors[18][1]-7,0,''))
            if intro and intro.height>50:
                save_webp(intro,outdir/'shared.webp')
                for q in (18,19,20):
                    if str(q) in items:items[str(q)]['shared']=f'assets/questions/{e["id"]}/shared.webp'
                log.append(f'shared: {intro.width}x{intro.height}')
    (outdir/'quality-check.txt').write_text('\n'.join(log)+'\n',encoding='utf8')
    print(f'{e["id"]}: {len(items)}/20 captured, {len(pdf):,} original PDF bytes',flush=True)
    doc.close()
    return items


def make_review(manifest):
    """Human-readable sheet to spot questions cut into the wrong image."""
    cards=[]
    for paper,items in manifest['papers'].items():
        for q,meta in items.items():
            img=meta['image'].replace('assets/questions/','')
            cards.append(f'<article><h3>{html.escape(paper)} · 第 {int(q)} 題</h3><p>原卷 PDF 第 {meta["start_page"]} 頁 · {meta["size"][0]}×{meta["size"][1]} px</p><img loading="lazy" src="{html.escape(img)}" alt="{html.escape(paper)} 第 {int(q)} 題截圖" /></article>')
    page='<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>學測數學｜逐題裁切品質檢查</title><style>body{font-family:system-ui,sans-serif;max-width:1100px;margin:auto;padding:25px;background:#f3f6ef;color:#153f38}article{background:white;padding:20px;border:1px solid #dce5da;margin:20px 0;border-radius:14px}article img{display:block;max-width:100%;height:auto}h3{margin:0}p{color:#526b62}</style><h1>學測數學｜逐題擷取結果</h1><p>這是自動裁切結果，請人工逐題檢查：開頭與結尾是否完整、有無漏掉圖形／共用題組題幹；自動擷取不代表已經校對。</p>'+'\n'.join(cards)+'</html>'
    (ASSETS/'review.html').write_text(page,encoding='utf8')

def main():
    ASSETS.mkdir(parents=True,exist_ok=True)
    manifest={'source':'CEEC original PDF question crops (automatically generated; human review recommended)','papers':{},'schema':1}
    failed=[]
    for e in EXAMS:
        try:
            manifest['papers'][e['id']]=build(e)
        except Exception as ex:
            failed.append(f'{e["id"]}: {ex}')
            print('ERROR',failed[-1],file=sys.stderr,flush=True)
    (ASSETS/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    make_review(manifest)
    # A manifest is written even if only some PDF URLs are reachable.
    count=sum(len(x) for x in manifest['papers'].values())
    print(f'CREATED {count}/260 potential question images across {len(manifest["papers"])} papers')
    if failed:
        print('FAILED PAPERS:',*failed,sep='\n',file=sys.stderr)
        sys.exit(1 if count==0 else 0)

if __name__=='__main__':main()
