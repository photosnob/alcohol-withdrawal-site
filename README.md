# alcoholwithdrawal.co

Alcohol Withdrawal & Drinking Problems, moved off WordPress to a static site on Cloudflare Workers. Every push to `main` deploys.

The pages in `public/` are the live WordPress site's own HTML, styles, scripts and images (Newspaper theme and plugin files kept at their WordPress paths, so everything looks the same). Changes made in the move:

- Google AdSense ads are kept as they were.
- The PureChat live chat and the Mailmunch email signup were removed.
- The search boxes go to `/search/`, a static search ([Pagefind](https://pagefind.app)) built from the articles and pages on each deploy.
- Leftover pages from an old business-listing plugin (`/pricing-plan/`, `/submit-listing/`, `/payment-*`, `/listing-author/`) and WordPress's `/sample-page/` were removed and redirect to the home page (`public/_redirects`).
- The theme's next/previous arrows on article blocks were hidden: they loaded more posts from WordPress, which no longer exists. Every article is still reachable from the category, tag and page-2+ listings.
- `public/sitemap.xml` and `public/robots.txt` replace the WordPress sitemap plugin's.

## Editing

Each page is `public/<url>/index.html` (the home page is `public/index.html`). Edit the HTML directly, or ask Claude to. Images go in `public/wp-content/uploads/`. Cloudflare Workers serves files up to 25 MiB each.

## Commands

```
npm install
npm run preview   # build the search index and serve locally
npm run deploy    # build and deploy by hand (normally Cloudflare does this on push)
```

Cloudflare build settings: build command `npm run build`, deploy command `npx wrangler deploy`.

`build-from-wordpress.py` is the one-time script that turned the WordPress copy into `public/`; it's kept for reference.
