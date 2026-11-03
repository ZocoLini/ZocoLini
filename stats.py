import collections
import datetime
import json
import os
import re
import urllib.parse
import urllib.request

GITLAB = "https://gitlab.com/api/v4"
EMAIL = "borjacastellano1@gmail.com"
WORK_REPOS = ["dashpay/rust-dashcore", "dashpay/platform"]
OWN_REPOS = ["ZocoLini/fee", "ZocoLini/ezffi", "ZocoLini/cuqdyn-c"]
PRIVATE_PROJECTS = [
    ("Custora", "noesisbit/zaisei", "app/"),
    ("aesmeralda", "noesisbit/esmeralda", "admin/"),
    ("salinasdoullo", "noesisbit/salinasdoullo", "web/"),
]


def get(url, headers):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers)) as res:
        return json.load(res), res.headers


def github(path):
    headers = {"Authorization": f"Bearer {os.environ['GH_TOKEN']}"}
    return get(f"https://api.github.com{path}", headers)[0]


def github_total(kind, query):
    return github(f"/search/{kind}?q={query}&per_page=1")["total_count"]


def gitlab(path):
    return get(f"{GITLAB}{path}", {"PRIVATE-TOKEN": os.environ["GITLAB_TOKEN"]})


def gitlab_pages(path):
    page = "1"
    while page:
        sep = "&" if "?" in path else "?"
        items, headers = gitlab(f"{path}{sep}per_page=100&page={page}")
        yield from items
        page = headers.get("X-Next-Page")


def gitlab_commits():
    author = urllib.parse.quote(EMAIL)
    commits = set()
    for project in gitlab_pages("/projects?membership=true&simple=true"):
        path = f"/projects/{project['id']}/repository/commits?all=true&author={author}"
        commits |= {c["id"] for c in gitlab_pages(path) if c["author_email"] == EMAIL}
    return len(commits)


def day(date):
    return datetime.date.fromisoformat(date[:10]).strftime("%b %-d, %Y")


def work_release(repo):
    releases = [r for r in github(f"/repos/{repo}/releases?per_page=100") if not r["prerelease"]]
    for new, old in zip(releases, releases[1:]):
        window = f"{old['published_at']}..{new['published_at']}"
        if github_total("issues", f"repo:{repo}+author:ZocoLini+type:pr+is:merged+merged:{window}"):
            return repo, new["tag_name"], new["html_url"], new["published_at"]


def own_release(repo):
    tag = github(f"/repos/{repo}/tags?per_page=1")[0]
    date = github(f"/repos/{repo}/commits/{tag['commit']['sha']}")["commit"]["committer"]["date"]
    return repo, tag["name"], f"https://github.com/{repo}/releases/tag/{tag['name']}", date


def private_release(name, path, prefix):
    tags, _ = gitlab(f"/projects/{urllib.parse.quote(path, safe='')}/repository/tags?search={urllib.parse.quote('^' + prefix)}&order_by=updated")
    return name, tags[0]["name"], tags[0]["commit"]["committed_date"]


def releases():
    public = [work_release(r) for r in WORK_REPOS] + [own_release(r) for r in OWN_REPOS]
    public = sorted(filter(None, public), key=lambda r: r[3], reverse=True)
    private = sorted((private_release(*p) for p in PRIVATE_PROJECTS), key=lambda r: r[2], reverse=True)
    lines = [
        f"* **[{repo.split('/')[1]}](https://github.com/{repo})** [`{tag.split('/')[-1]}`]({link}) · {day(date)}"
        for repo, tag, link, date in public
    ]
    lines += [f"* **{name}** `{tag.split('/')[-1]}` · {day(date)} · *freelance, private repo*" for name, tag, date in private]
    return "\n".join(lines)


def open_source():
    repos = collections.Counter()
    page = 1
    while True:
        query = "author:ZocoLini+type:pr+is:merged+-user:ZocoLini+-user:dashpay+-user:ChandoCar"
        items = github(f"/search/issues?q={query}&per_page=100&page={page}")["items"]
        repos.update(i["repository_url"].split("/repos/")[1] for i in items)
        if len(items) < 100:
            break
        page += 1
    return "\n".join(
        f"* **[{repo.split('/')[1]}](https://github.com/{repo})** · "
        f"[{count} merged PRs](https://github.com/{repo}/pulls?q=is%3Apr+is%3Amerged+author%3AZocoLini)"
        for repo, count in repos.most_common()
    )


def fill(readme, marker, text):
    return re.sub(rf"<!-- {marker} -->.*<!-- /{marker} -->", f"<!-- {marker} -->{text}<!-- /{marker} -->", readme, flags=re.S)


prs = github_total("issues", "author:ZocoLini+type:pr+is:merged")
commits = github_total("commits", "author:ZocoLini")

line = f"{prs:,} merged PRs and {commits:,} commits on GitHub, plus {gitlab_commits():,} commits on GitLab."
readme = open("README.md").read()
readme = fill(readme, "stats", line)
readme = fill(readme, "releases", f"\n{releases()}\n")
readme = fill(readme, "open-source", f"\n{open_source()}\n")
open("README.md", "w").write(readme)
print(line)
