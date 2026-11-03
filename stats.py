import collections
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
    ("Custora", "noesisbit/zaisei", "app/", "private, freelance"),
    ("aesmeralda", "noesisbit/esmeralda", "admin/", "private, freelance"),
    ("salinasdoullo", "noesisbit/salinasdoullo", "web/", "private, freelance"),
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


def work_release(repo):
    releases = [r for r in github(f"/repos/{repo}/releases?per_page=100") if not r["prerelease"]]
    for new, old in zip(releases, releases[1:]):
        window = f"{old['published_at']}..{new['published_at']}"
        if github_total("issues", f"repo:{repo}+author:ZocoLini+type:pr+is:merged+merged:{window}"):
            return f"[{repo}](https://github.com/{repo})", f"[{new['tag_name']}]({new['html_url']})", new["published_at"][:10]


def own_release(repo):
    tag = github(f"/repos/{repo}/tags?per_page=1")[0]
    date = github(f"/repos/{repo}/commits/{tag['commit']['sha']}")["commit"]["committer"]["date"]
    link = f"https://github.com/{repo}/releases/tag/{tag['name']}"
    return f"[{repo.split('/')[1]}](https://github.com/{repo})", f"[{tag['name']}]({link})", date[:10]


def private_release(name, path, prefix, label):
    tags, _ = gitlab(f"/projects/{urllib.parse.quote(path, safe='')}/repository/tags?search={urllib.parse.quote('^' + prefix)}&order_by=updated")
    return f"{name} *({label})*", tags[0]["name"], tags[0]["commit"]["committed_date"][:10]


def releases():
    rows = [work_release(r) for r in WORK_REPOS] + [own_release(r) for r in OWN_REPOS]
    rows += [private_release(*p) for p in PRIVATE_PROJECTS]
    rows = sorted(filter(None, rows), key=lambda row: row[2], reverse=True)
    return "| Project | Release | Date |\n|---|---|---|\n" + "\n".join(f"| {' | '.join(row)} |" for row in rows)


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
    rows = "\n".join(
        f"| [{repo}](https://github.com/{repo}) | [{count}](https://github.com/{repo}/pulls?q=is%3Apr+is%3Amerged+author%3AZocoLini) |"
        for repo, count in repos.most_common()
    )
    return "| Project | Merged PRs |\n|---|---|\n" + rows


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
