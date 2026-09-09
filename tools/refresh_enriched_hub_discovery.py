"""Refresh only enriched hub entries, preserving the existing discovery inventory."""
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
import argparse
import html
import json
import re
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--modified', required=True, help='ISO timestamp with timezone of this content release')
    args = parser.parse_args()
    changed = datetime.fromisoformat(args.modified)
    assert changed.tzinfo is not None
    targets = json.loads((ROOT/'tools/reports/hub-enrichment/generation.json').read_text(encoding='utf-8'))['targets']
    by_url = {}
    for item in targets:
        s = BeautifulSoup((ROOT/item['path']).read_text(encoding='utf-8'),'html.parser')
        by_url[s.select_one('[rel=canonical]')['href']] = s.select_one('meta[name=description]')['content']
    source = (ROOT/'sitemap.xml').read_text(encoding='utf-8')
    original_urls = [x.text for x in ET.fromstring(source).findall('{*}url/{*}loc')]
    count = 0
    def sitemap_block(m):
        nonlocal count
        block = m.group(0)
        url = html.unescape(re.search(r'<loc>(.*?)</loc>',block).group(1))
        if url not in by_url: return block
        count += 1
        return re.sub(r'<lastmod>.*?</lastmod>','<lastmod>'+changed.date().isoformat()+'</lastmod>',block)
    updated = re.sub(r'<url>.*?</url>',sitemap_block,source,flags=re.S)
    assert count == len(by_url)
    assert original_urls == [x.text for x in ET.fromstring(updated).findall('{*}url/{*}loc')]
    (ROOT/'sitemap.xml').write_text(updated,encoding='utf-8',newline='\n')
    source = (ROOT/'rss.xml').read_text(encoding='utf-8')
    rss_count = 0
    def rss_block(m):
        nonlocal rss_count
        block = m.group(0)
        url = html.unescape(re.search(r'<link>(.*?)</link>',block).group(1))
        if url not in by_url: return block
        rss_count += 1
        block = re.sub(r'<description>.*?</description>',lambda _: '<description>'+html.escape(by_url[url],quote=False)+'</description>',block,flags=re.S)
        return re.sub(r'<pubDate>.*?</pubDate>','<pubDate>'+format_datetime(changed)+'</pubDate>',block)
    updated = re.sub(r'<item>.*?</item>',rss_block,source,flags=re.S)
    updated = re.sub(r'<lastBuildDate>.*?</lastBuildDate>','<lastBuildDate>'+format_datetime(changed)+'</lastBuildDate>',updated)
    assert rss_count == len(by_url)
    assert len(ET.fromstring(source).findall('./channel/item')) == len(ET.fromstring(updated).findall('./channel/item'))
    (ROOT/'rss.xml').write_text(updated,encoding='utf-8',newline='\n')
    print(json.dumps({'sitemap_total':len(original_urls),'updated_sitemap_entries':count,'updated_rss_entries':rss_count,'rss_total':len(ET.fromstring(updated).findall('./channel/item'))}))

if __name__ == '__main__': main()
