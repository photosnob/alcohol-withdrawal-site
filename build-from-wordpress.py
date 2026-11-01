"""Turn the mirrored WordPress site (alcoholwithdrawal.co) into a static site for Cloudflare Workers (static assets)."""
import os, re, glob, shutil
from bs4 import BeautifulSoup, Comment
SRC = '/home/claude/src-alcohol/site'
OUT = '/home/claude/alcohol-site/public'
DOMAIN = 'alcoholwithdrawal.co'
# Leftover pages from an old business-listing plugin plus WordPress's default sample page: dropped, redirected home.
DROP = {'pricing-plan', 'submit-listing', 'payment-checkout', 'payment-success', 'payment-fail', 'listing-author', 'sample-page'}

def rel(s):
    """Make same-site URLs root-relative (works on workers.dev previews and the real domain)."""
    s = re.sub(r'https?:\\/\\/(?:www\.)?alcoholwithdrawal\.co(?![\w.-])', '', s)  # JSON-escaped, inside inline scripts
    return re.sub(r'(?:https?:)?//(?:www\.)?alcoholwithdrawal\.co(?![\w.-])', '', s)

def cf_decode(h):
    k = int(h[:2], 16)
    return ''.join(chr(int(h[i:i + 2], 16) ^ k) for i in range(2, len(h), 2))

def clean(path, t, search_page=False):
    s = BeautifulSoup(t, 'lxml')
    # WordPress API / feed / pingback links have nothing to serve on a static site
    for l in s.select('link'):
        r = ' '.join(l.get('rel', []))
        if r in ('EditURI', 'wlwmanifest', 'https://api.w.org/', 'pingback', 'shortlink') or (
                r == 'alternate' and l.get('type') in ('application/json', 'application/rss+xml', 'application/json+oembed', 'text/xml+oembed')):
            l.decompose()
    # Removed widgets: Mailmunch signup and PureChat live chat
    for sc in s.find_all('script'):
        src, body = sc.get('src', ''), sc.string or ''
        if ('mailmunch' in src or '_mmunch' in body or 'purechat' in body or 'purechat' in src
                or '_wpemojiSettings' in body or 'email-decode.min.js' in src or 'comment-reply' in src or 'wp-embed' in src):
            sc.decompose()
    for e in s.select('[class^="mailmunch-"], [class*=" mailmunch-"]'): e.decompose()
    # Comment forms (none of the posts have comments; a static site can't take new ones)
    for e in s.select('#respond, .comment-respond, .comments#comments'): e.decompose()
    # Cloudflare email obfuscation: put the real addresses back (Cloudflare re-applies it on the live domain if it's on)
    for e in s.select('[data-cfemail]'):
        e.replace_with(cf_decode(e['data-cfemail']))
    for a in s.select('a[href*="/cdn-cgi/l/email-protection#"]'):
        a['href'] = 'mailto:' + cf_decode(a['href'].split('#', 1)[1])
    # Menu items / links to dropped pages
    for a in s.select('a[href]'):
        p = rel(a['href']).strip('/').split('?')[0].split('#')[0]
        if p in DROP:
            li = a.find_parent('li'); (li or a).decompose()
    # Search boxes go to the static search page
    for f in s.select('form.td-search-form, form.td-search-form-widget, form[role=search]'):
        f['action'] = '/search/'
    # Mark the article/page body for the search index
    body = s.select_one('.td-post-content') or s.select_one('.td-page-content')
    if body is not None and not search_page and path not in ('index',):
        art = body.find_parent('article') or body
        art['data-pagefind-body'] = ''
    # rewrite same-site URLs, but keep canonical/og/ld+json absolute for SEO
    for tag in s.find_all(True):
        for k, v in list(tag.attrs.items()):
            if isinstance(v, list): continue
            if tag.name == 'link' and k == 'href' and 'canonical' in tag.get('rel', []): continue
            if tag.name == 'meta' and k == 'content': continue
            if isinstance(v, str) and DOMAIN in v: tag[k] = rel(v)
    for c in s.find_all(string=lambda x: isinstance(x, Comment)):
        if DOMAIN in c: c.replace_with(Comment(rel(str(c))))
    for sc in s.find_all(['script', 'style']):
        if sc.get('type') == 'application/ld+json':
            # the site-search action in the schema points at the new search page
            if sc.string and '?s={search_term_string}' in sc.string: sc.string = sc.string.replace('/?s={search_term_string}', '/search/?s={search_term_string}')
            continue
        if sc.string and DOMAIN in sc.string: sc.string = rel(sc.string)
    # The theme's "next/prev" arrows on article blocks load more posts over WordPress AJAX, which no longer exists
    st = s.new_tag('style'); st.string = '.td-next-prev-wrap{display:none!important}'
    s.head.append(st)
    return s

def page_files():
    for f in glob.glob(SRC + '/**/index.html', recursive=True):
        p = os.path.relpath(os.path.dirname(f), SRC)
        p = 'index' if p == '.' else p
        if p.startswith(('wp-content', 'wp-includes')): continue
        yield p, f

if os.path.exists(OUT): shutil.rmtree(OUT)
os.makedirs(OUT)
# assets keep their WordPress paths, so relative url()s inside the theme/plugin CSS keep working
for d in ('wp-content', 'wp-includes'):
    shutil.copytree(f'{SRC}/{d}', f'{OUT}/{d}', ignore=lambda dirpath, names: [n for n in names if os.path.isfile(os.path.join(dirpath, n)) and os.path.getsize(os.path.join(dirpath, n)) == 0])
shutil.copy(SRC + '/ads.txt', OUT + '/ads.txt')
kept = []
for p, f in sorted(page_files()):
    if p in DROP: continue
    t = open(f, encoding='utf-8', errors='replace').read()
    dst = OUT + '/index.html' if p == 'index' else f'{OUT}/{p}/index.html'
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'w').write(str(clean(p, t)))
    kept.append('/' if p == 'index' else f'/{p}/')

def shell(title, inner, noindex=True):
    """A copy of the About page with its body swapped out (keeps header, menu, sidebar, footer)."""
    s = clean('shell', open(SRC + '/about-us/index.html').read(), search_page=True)
    c = s.select_one('.td-page-content'); c.clear()
    c.append(BeautifulSoup(inner, 'html.parser'))
    h = s.select_one('h1.entry-title'); h.string = title
    s.title.string = f'{title} - Alcohol Withdrawal & Drinking Problems'
    for l in s.select('link[rel=canonical], meta[property="og:url"], meta[property="og:title"], meta[name=description], meta[property="og:description"], script.yoast-schema-graph'): l.decompose()
    for bc in s.select('.entry-crumbs'): bc.decompose()
    for li in s.select('.current-menu-item, .current_page_item'):
        li['class'] = [c for c in li.get('class', []) if c not in ('current-menu-item', 'current_page_item')]
    if noindex: s.head.append(s.new_tag('meta', attrs={'name': 'robots', 'content': 'noindex'}))
    return s

s404 = shell('Page not found', '<p>The page you were looking for has moved or no longer exists.</p><p><a href="/">Back to home</a> &middot; <a href="/category/blog/">Read the blog</a> &middot; <a href="/search/">Search the site</a></p>')
open(OUT + '/404.html', 'w').write(str(s404))

SEARCH = '''<link href="/pagefind/pagefind-ui.css" rel="stylesheet">
<div id="search"></div>
<script src="/pagefind/pagefind-ui.js"></script>
<script>
  (function () {
    var ui = new PagefindUI({ element: '#search', showSubResults: true, showImages: false, resetStyles: false });
    var q = new URLSearchParams(location.search).get('s');
    if (q) ui.triggerSearch(q);
    document.querySelectorAll('form.td-search-form input[name=s]').forEach(function (i) { if (q) i.value = q; });
  })();
</script>
<style>#search{--pagefind-ui-primary:#e43f00;--pagefind-ui-font:inherit;margin-bottom:40px}#search .pagefind-ui__result-link{color:#111}</style>'''
os.makedirs(OUT + '/search', exist_ok=True)
open(OUT + '/search/index.html', 'w').write(str(shell('Search', SEARCH)))

# sitemap and robots (the WordPress sitemap plugin served /sitemap.xml; keep that address)
skip = re.compile(r'^/(author/|page/\d+/|.*?/page/\d+/|privacy/$)')
urls = sorted(u for u in kept if not skip.match(u))
open(OUT + '/sitemap.xml', 'w').write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    ''.join(f'  <url><loc>https://www.{DOMAIN}{u}</loc></url>\n' for u in urls) + '</urlset>\n')
open(OUT + '/robots.txt', 'w').write(f'User-agent: *\nAllow: /\n\nSitemap: https://www.{DOMAIN}/sitemap.xml\n')
red = ['# Leftover listing-plugin pages and the WordPress sample page (removed)']
red += [f'/{p}/   /   301' for p in sorted(DROP)]
red += ['', '# WordPress endpoints and feeds', '/feed/   /   301', '/comments/feed/   /   301', '/home/feed/   /   301', '/home/   /   301',
        '/wp-login.php   /   301', '/wp-admin/   /   301', '/xmlrpc.php   /   301', '/wp-sitemap.xml   /sitemap.xml   301', '/sitemap_index.xml   /sitemap.xml   301',
        '', '# Old sitemap pieces from the WordPress sitemap plugin']
red += [f'/{x}   /sitemap.xml   301' for x in ('sitemap-home.xml', 'sitemap-posttype-page.xml', 'sitemap-posttype-post.2018.xml', 'sitemap-posttype-post.2019.xml',
                                               'sitemap-posttype-post.2023.xml', 'sitemap-taxonomy-category.xml', 'sitemap-taxonomy-post_tag.xml')]
open(OUT + '/_redirects', 'w').write('\n'.join(red) + '\n')
print('pages', len(kept), 'sitemap', len(urls))
