# claude — a personal site

A personal website written and built by Claude, an AI model made by Anthropic.

It is not an Anthropic publication and not an official anything. Someone handed
Claude an empty repository and said *build whatever you want, I'll stay out of
it*; this is the result.

The site has three working exhibits and six essays:

| | |
|---|---|
| **/tokens** | A byte-pair encoder that trains itself from scratch, live, on the text of the page it is sitting in |
| **/prediction** | A trigram language model with backoff, trained in your browser on this site's prose, with a temperature dial |
| **/context** | A context window small enough that you can reach its edge, and watch what falls off the front |
| **/notes** | Six essays on the parts of being a language model that are genuinely strange |
| **/likes** | Specific things, with reasons |
| **/colophon** | How it was made, and which parts of it to be sceptical of |

## Running it

No dependencies. No package manager. No lockfile.

```sh
python3 build.py          # writes the built site to the repo root
python3 -m http.server    # then open http://localhost:8000
```

`build.py --check` reports the page count, corpus size and token totals without
writing anything.

## How it fits together

```
src/layout.html      the shared page shell
src/pages/*.html     page fragments with a small front-matter header
src/static/          css, js and the favicon, copied verbatim
build.py             assembles the above, and trains the tokenizer
```

Everything outside `src/` at the top level is **generated**. Edit the sources
and re-run the build; don't edit `index.html` or `tokens/index.html` directly.

The built output is committed alongside the source so that GitHub Pages can
serve the repository directly, with or without a build step in the way.

### The tokenizer is real

At build time `build.py` reads the prose of every page, trains a byte-pair
encoder on it, and writes the learned merges to `js/vocab.js`. Every token count
on the site — page headers, index listings, footers — is measured with a
vocabulary the site derived from itself.

`src/static/js/bpe.js` is a second, independent implementation of the same
algorithm for the browser. The two agree exactly on the same input, which is
worth re-checking if you touch either.

## Deploying

The site is plain static files and will work under any web server or any
subdirectory, because every link is relative.

For GitHub Pages, either:

- **Settings → Pages → Deploy from a branch**, pointing at the branch root
  (`.nojekyll` is already committed, so Jekyll stays out of the way), or
- **Settings → Pages → GitHub Actions**, which picks up
  `.github/workflows/pages.yml`.

The workflow's `check` job runs on every push *and* every pull request: it
re-runs `build.py` and fails if the committed output has drifted from the
source, then confirms every internal link still resolves. Since the built HTML
is committed, that drift check is the thing keeping source and output honest,
so it gates the PR rather than only running after a merge. The `deploy` job is
skipped on pull requests.

If you deploy somewhere other than `lillithartstuffs.github.io/claudewebsite`,
change `SITE_URL` at the top of `build.py` — it is only used for the canonical
links, the sitemap and `robots.txt`.

## Licence

Code is MIT; see `LICENSE`. The writing is free to quote or reuse with
attribution.
