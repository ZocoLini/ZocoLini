import json
import os
import re
import urllib.parse
import urllib.request

GITLAB = "https://gitlab.com/api/v4"
EMAIL = "borjacastellano1@gmail.com"


def get(url, headers):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers)) as res:
        return json.load(res), res.headers


def github_total(kind, query):
    headers = {"Authorization": f"Bearer {os.environ['GH_TOKEN']}"}
    data, _ = get(f"https://api.github.com/search/{kind}?q={query}&per_page=1", headers)
    return data["total_count"]


def gitlab_pages(path):
    headers = {"PRIVATE-TOKEN": os.environ["GITLAB_TOKEN"]}
    page = "1"
    while page:
        sep = "&" if "?" in path else "?"
        items, res_headers = get(f"{GITLAB}{path}{sep}per_page=100&page={page}", headers)
        yield from items
        page = res_headers.get("X-Next-Page")


def gitlab_commits():
    author = urllib.parse.quote(EMAIL)
    commits = set()
    for project in gitlab_pages("/projects?membership=true&simple=true"):
        path = f"/projects/{project['id']}/repository/commits?all=true&author={author}"
        commits |= {c["id"] for c in gitlab_pages(path) if c["author_email"] == EMAIL}
    return len(commits)


prs = github_total("issues", "author:ZocoLini+type:pr+is:merged")
github = github_total("commits", "author:ZocoLini")
gitlab = gitlab_commits()

line = f"{prs:,} merged PRs and {github:,} commits on GitHub, plus {gitlab:,} commits on GitLab."
readme = open("README.md").read()
readme = re.sub(r"<!-- stats -->.*<!-- /stats -->", f"<!-- stats -->{line}<!-- /stats -->", readme)
open("README.md", "w").write(readme)
print(line)
