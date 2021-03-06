# The MIT License (MIT)
#
# Copyright (c) 2017 Scott Shawcroft for Adafruit Industries
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
import datetime
import re
import sys

import requests

from adabot import github_requests as github
from adabot import travis_requests as travis


# Define constants for error strings to make checking against them more robust:
ERROR_ENABLE_TRAVIS = "Unable to enable Travis build"
ERROR_README_DOWNLOAD_FAILED = "Failed to download README"
ERROR_README_IMAGE_MISSING_ALT = "README image missing alt text"
ERROR_README_DUPLICATE_ALT_TEXT = "README has duplicate alt text"
ERROR_README_MISSING_DISCORD_BADGE = "README missing Discord badge"
ERROR_README_MISSING_RTD_BADGE = "README missing ReadTheDocs badge"
ERROR_README_MISSING_TRAVIS_BADGE = "README missing Travis badge"
ERROR_PYFILE_DOWNLOAD_FAILED = "Failed to download .py code file"
ERROR_PYFILE_MISSING_STRUCT = ".py file contains reference to import ustruct" \
" without reference to import struct.  See issue " \
"https://github.com/adafruit/circuitpython/issues/782"
ERROR_MISMATCHED_READTHEDOCS = "Mismatched readthedocs.yml"
ERROR_MISSING_EXAMPLE_FILES = "Missing .py files in examples folder"
ERROR_MISSING_EXAMPLE_FOLDER = "Missing examples folder"
ERROR_MISSING_LIBRARIANS = "Likely missing CircuitPythonLibrarians team."
ERROR_MISSING_LICENSE = "Missing license."
ERROR_MISSING_LINT = "Missing lint config"
ERROR_MISSING_CODE_OF_CONDUCT = "Missing CODE_OF_CONDUCT.md"
ERROR_MISSING_README_RST = "Missing README.rst"
ERROR_MISSING_READTHEDOCS = "Missing readthedocs.yml"
ERROR_MISSING_TRAVIS_CONFIG = "Missing .travis.yml"
ERROR_NOT_IN_BUNDLE = "Not in bundle."
ERROR_OLD_TRAVIS_CONFIG = "Old travis config"
ERROR_TRAVIS_DOESNT_KNOW_REPO = "Travis doesn't know of repo"
ERROR_TRAVIS_ENV = "Unable to read Travis env variables"
ERROR_TRAVIS_GITHUB_TOKEN = "Unable to find or create (no auth) GITHUB_TOKEN env variable"
ERROR_TRAVIS_TOKEN_CREATE = "Token creation failed"
ERROR_UNABLE_PULL_REPO_CONTENTS = "Unable to pull repo contents"
ERROR_UNABLE_PULL_REPO_DETAILS = "Unable to pull repo details"
ERRRO_UNABLE_PULL_REPO_EXAMPLES = "Unable to retrieve examples folder contents"
ERROR_WIKI_DISABLED = "Wiki should be disabled"
ERROR_ONLY_ALLOW_MERGES = "Only allow merges, disallow rebase and squash"
ERROR_RTD_SUBPROJECT_FAILED = "Failed to list CircuitPython subprojects on ReadTheDocs"
ERROR_RTD_SUBPROJECT_MISSING = "ReadTheDocs missing as a subproject on CircuitPython"
ERROR_RTD_ADABOT_MISSING = "ReadTheDocs project missing adabot as owner"
ERROR_RTD_VALID_VERSIONS_FAILED = "Failed to fetch ReadTheDocs valid versions"
ERROR_RTD_FAILED_TO_LOAD_BUILDS = "Unable to load builds webpage"
ERROR_RTD_FAILED_TO_LOAD_BUILD_INFO = "Failed to load build info"
ERROR_RTD_OUTPUT_HAS_WARNINGS = "ReadTheDocs latest build has warnings and/or errors"
ERROR_RTD_AUTODOC_FAILED = "Autodoc failed on ReadTheDocs. (Likely need to automock an import.)"
ERROR_RTD_SPHINX_FAILED = "Sphinx missing files"
ERROR_GITHUB_RELEASE_FAILED = "Failed to fetch latest release from GitHub"
ERROR_RTD_MISSING_LATEST_RELEASE = "ReadTheDocs missing the latest release. (Ignore me! RTD doesn't update when a new version is released. Only on pushes.)"
ERROR_DRIVERS_PAGE_DOWNLOAD_FAILED = "Failed to download drivers page from CircuitPython docs"
ERROR_DRIVERS_PAGE_DOWNLOAD_MISSING_DRIVER = "CircuitPython drivers page missing driver"
ERROR_UNABLE_PULL_REPO_DIR = "Unable to pull repository directory"
ERROR_UNABLE_PULL_REPO_EXAMPLES = "Unable to pull repository examples files"

# These are warnings or errors that sphinx generate that we're ok ignoring.
RTD_IGNORE_NOTICES = ("WARNING: html_static_path entry", "WARNING: nonlocal image URI found:")

# Constant for bundle repo name.
BUNDLE_REPO_NAME = "Adafruit_CircuitPython_Bundle"

# Repos to ignore for validation they exist in the bundle.  Add repos by their
# full name on Github (like Adafruit_CircuitPython_Bundle).
BUNDLE_IGNORE_LIST = [BUNDLE_REPO_NAME]

# Cache CircuitPython's subprojects on ReadTheDocs so its not fetched every repo check.
rtd_subprojects = None

# Cache the CircuitPython driver page so we can make sure every driver is linked to.
core_driver_page = None

def parse_gitmodules(input_text):
    """Parse a .gitmodules file and return a list of all the git submodules
    defined inside of it.  Each list item is 2-tuple with:
      - submodule name (string)
      - submodule variables (dictionary with variables as keys and their values)
    The input should be a string of text with the complete representation of
    the .gitmodules file.

    See this for the format of the .gitmodules file, it follows the git config
    file format:
      https://www.kernel.org/pub/software/scm/git/docs/git-config.html

    Note although the format appears to be like a ConfigParser-readable ini file
    it is NOT possible to parse with Python's built-in ConfigParser module.  The
    use of tabs in the git config format breaks ConfigParser, and the subsection
    values in double quotes are completely lost.  A very basic regular
    expression-based parsing logic is used here to parse the data.  This parsing
    is far from perfect and does not handle escaping quotes, line continuations
    (when a line ends in '\;'), etc.  Unfortunately the git config format is
    surprisingly complex and no mature parsing modules are available (outside
    the code in git itself).
    """
    # Assume no results if invalid input.
    if input_text is None:
        return []
    # Define a regular expression to match a basic submodule section line and
    # capture its subsection value.
    submodule_section_re = '^\[submodule "(.+)"\]$'
    # Define a regular expression to match a variable setting line and capture
    # the variable name and value.  This does NOT handle multi-line or quote
    # escaping (far outside the abilities of a regular expression).
    variable_re = '^\s*([a-zA-Z0-9\-]+) =\s+(.+?)\s*$'
    # Process all the lines to parsing submodule sections and the variables
    # within them as they're found.
    results = []
    submodule_name = None
    submodule_variables = {}
    for line in input_text.splitlines():
        submodule_section_match = re.match(submodule_section_re, line, flags=re.IGNORECASE)
        variable_match = re.match(variable_re, line)
        if submodule_section_match:
            # Found a new section.  End the current one if it had data and add
            # it to the results, then start parsing a new section.
            if submodule_name is not None:
                results.append((submodule_name, submodule_variables))
            submodule_name = submodule_section_match.group(1)
            submodule_variables = {}
        elif variable_match:
            # Found a variable, add it to the current section variables.
            # Force the variable name to lower case as variable names are
            # case-insensitive in git config sections and this makes later
            # processing easier (can assume lower-case names to find values).
            submodule_variables[variable_match.group(1).lower()] = variable_match.group(2)
    # Add the last parsed section if it exists.
    if submodule_name is not None:
        results.append((submodule_name, submodule_variables))
    return results

def get_bundle_submodules():
    """Query Adafruit_CircuitPython_Bundle repository for all the submodules
    (i.e. modules included inside) and return a list of the found submodules.
    Each list item is a 2-tuple of submodule name and a dict of submodule
    variables including 'path' (location of submodule in bundle) and
    'url' (URL to git repository with submodule contents).
    """
    # Assume the bundle repository is public and get the .gitmodules file
    # without any authentication or Github API usage.  Also assumes the
    # master branch of the bundle is the canonical source of the bundle release.
    result = requests.get('https://raw.githubusercontent.com/adafruit/Adafruit_CircuitPython_Bundle/master/.gitmodules')
    if result.status_code != 200:
        raise RuntimeError('Failed to access bundle .gitmodules file from GitHub!')
    return parse_gitmodules(result.text)

def sanitize_url(url):
    """Convert a Github repository URL into a format which can be compared for
    equality with simple string comparison.  Will strip out any leading URL
    scheme, set consistent casing, and remove any optional .git suffix.  The
    attempt is to turn a URL from Github (which can be one of many different
    schemes with and without suffxes) into canonical values for easy comparison.
    """
    # Make the url lower case to perform case-insensitive comparisons.
    # This might not actually be correct if Github cares about case (assumption
    # is no Github does not, but this is unverified).
    url = url.lower()
    # Strip out any preceding http://, https:// or git:// from the URL to
    # make URL comparisons safe (probably better to explicitly parse using
    # a URL module in the future).
    scheme_end = url.find('://')
    if scheme_end >= 0:
        url = url[scheme_end:]
    # Strip out any .git suffix if it exists.
    if url.endswith('.git'):
        url = url[:-4]
    return url

def is_repo_in_bundle(repo_clone_url, bundle_submodules):
    """Return a boolean indicating if the specified repository (the clone URL
    as a string) is in the bundle.  Specify bundle_submodules as a dictionary
    of bundle submodule state returned by get_bundle_submodules.
    """
    # Sanitize url for easy comparison.
    repo_clone_url = sanitize_url(repo_clone_url)
    # Search all the bundle submodules for any that have a URL which matches
    # this clone URL.  Not the most efficient search but it's a handful of
    # items in the bundle.
    for submodule in bundle_submodules:
        name, variables = submodule
        submodule_url = variables.get('url', '')
        # Compare URLs and skip to the next submodule if it's not a match.
        # Right now this is a case sensitive compare, but perhaps it should
        # be insensitive in the future (unsure if Github repos are sensitive).
        if repo_clone_url != sanitize_url(submodule_url):
            continue
        # URLs matched so now check if the submodule is placed in the libraries
        # subfolder of the bundle.  Just look at the path from the submodule
        # state.
        if variables.get('path', '').startswith('libraries/'):
            # Success! Found the repo as a submodule of the libraries folder
            # in the bundle.
            return True
    # Failed to find the repo as a submodule of the libraries folders.
    return False

def list_repos():
    """Return a list of all Adafruit repositories that start with
    Adafruit_CircuitPython.  Each list item is a dictionary of GitHub API
    repository state.
    """
    repos = []
    result = github.get("/search/repositories",
                        params={"q":"Adafruit_CircuitPython in:name fork:true",
                                "per_page": 100,
                                "sort": "updated",
                                "order": "asc"})
    while result.ok:
        links = result.headers["Link"]
        repos.extend(result.json()["items"])
        next_url = None
        for link in links.split(","):
            link, rel = link.split(";")
            link = link.strip(" <>")
            rel = rel.strip()
            if rel == "rel=\"next\"":
                next_url = link
                break
        if not next_url:
            break
        # Subsequent links have our access token already so we use requests directly.
        result = requests.get(link)

    return repos

def validate_repo_state(repo):
    """Validate a repository meets current CircuitPython criteria.  Expects
    a dictionary with a GitHub API repository state (like from the list_repos
    function).  Returns a list of string error messages for the repository.
    """
    global bundle_submodules
    if not (repo["owner"]["login"] == "adafruit" and
            repo["name"].startswith("Adafruit_CircuitPython")):
        return []
    full_repo = github.get("/repos/" + repo["full_name"])
    if not full_repo.ok:
        return [ERROR_UNABLE_PULL_REPO_DETAILS]
    full_repo = full_repo.json()
    errors = []
    if repo["has_wiki"]:
        errors.append(ERROR_WIKI_DISABLED)
    if not repo["license"]:
        errors.append(ERROR_MISSING_LICENSE)
    if not repo["permissions"]["push"]:
        errors.append(ERROR_MISSING_LIBRARIANS)
    if not is_repo_in_bundle(full_repo["clone_url"], bundle_submodules) and \
       not repo["name"] in BUNDLE_IGNORE_LIST:  # Don't assume the bundle will
                                                # bundle itself and possibly
                                                # other repos.
        errors.append(ERROR_NOT_IN_BUNDLE)
    if "allow_squash_merge" not in full_repo or full_repo["allow_squash_merge"] or full_repo["allow_rebase_merge"]:
        errors.append(ERROR_ONLY_ALLOW_MERGES)
    return errors

def validate_readme(repo, download_url):
    # We use requests because file contents are hosted by githubusercontent.com, not the API domain.
    contents = requests.get(download_url)
    if not contents.ok:
        return [ERROR_README_DOWNLOAD_FAILED]

    errors = []
    badges = {}
    current_image = None
    for line in contents.text.split("\n"):
        if line.startswith(".. image"):
            current_image = {}

        if line.strip() == "" and current_image is not None:
            if "alt" not in current_image:
                errors.append(ERROR_README_IMAGE_MISSING_ALT)
            elif current_image["alt"] in badges:
                errors.append(ERROR_README_DUPLICATE_ALT_TEXT)
            else:
                badges[current_image["alt"]] = current_image
            current_image = None
        elif current_image is not None:
            first, second, value = line.split(":", 2)
            key = first.strip(" .") + second.strip()
            current_image[key] = value.strip()

    if "Discord" not in badges:
        errors.append(ERROR_README_MISSING_DISCORD_BADGE)

    if "Documentation Status" not in badges:
        errors.append(ERROR_README_MISSING_RTD_BADGE)

    if "Build Status" not in badges:
        errors.append(ERROR_README_MISSING_TRAVIS_BADGE)

    return errors

def validate_py_for_ustruct(repo, download_url):
    """ For a .py file, look for usage of "import ustruct" and
        look for "import struct".  If the "import ustruct" is
        used with NO "import struct" generate an error.
    """
    # We use requests because file contents are hosted by githubusercontent.com, not the API domain.
    contents = requests.get(download_url)
    if not contents.ok:
        return [ERROR_PYFILE_DOWNLOAD_FAILED]

    errors = []

    lines = contents.text.split("\n")
    ustruct_lines = [l for l in lines if re.match(r"[\s]*import[\s][\s]*ustruct", l)]
    struct_lines = [l for l in lines if re.match(r"[\s]*import[\s][\s]*struct", l)]
    if ustruct_lines and not struct_lines:
        errors.append(ERROR_PYFILE_MISSING_STRUCT)

    return errors


def validate_contents(repo):
    """Validate the contents of a repository meets current CircuitPython
    criteria (within reason, functionality checks are not possible).  Expects
    a dictionary with a GitHub API repository state (like from the list_repos
    function).  Returns a list of string error messages for the repository.
    """
    if not (repo["owner"]["login"] == "adafruit" and
            repo["name"].startswith("Adafruit_CircuitPython")):
        return []
    if repo["name"] == BUNDLE_REPO_NAME:
        return []

    content_list = github.get("/repos/" + repo["full_name"] + "/contents/")
    if not content_list.ok:
        return [ERROR_UNABLE_PULL_REPO_CONTENTS]

    content_list = content_list.json()
    files = [x["name"] for x in content_list]

    errors = []
    if ".pylintrc" not in files:
        errors.append(ERROR_MISSING_LINT)

    if "CODE_OF_CONDUCT.md" not in files:
        errors.append(ERROR_MISSING_CODE_OF_CONDUCT)

    if "README.rst" not in files:
        errors.append(ERROR_MISSING_README_RST)
    else:
        readme_info = None
        for f in content_list:
            if f["name"] == "README.rst":
                readme_info = f
                break
        errors.extend(validate_readme(repo, readme_info["download_url"]))

    if ".travis.yml" in files:
        file_info = content_list[files.index(".travis.yml")]
        if file_info["size"] > 1000:
            errors.append(ERROR_OLD_TRAVIS_CONFIG)
    else:
        errors.append(ERROR_MISSING_TRAVIS_CONFIG)

    if "readthedocs.yml" in files or ".readthedocs.yml" in files:
        fn = "readthedocs.yml"
        if ".readthedocs.yml" in files:
            fn = ".readthedocs.yml"
        file_info = content_list[files.index(fn)]
        if file_info["sha"] != "f4243ad548bc5e4431f2d3c5d486f6c9c863888b":
            errors.append(ERROR_MISMATCHED_READTHEDOCS)
    else:
        errors.append(ERROR_MISSING_READTHEDOCS)

    #Check for an examples folder.
    dirs = [x["name"] for x in content_list if x["type"] == "dir"]
    if "examples" in dirs:
        # check for at least on .py file
        examples_list = github.get("/repos/" + repo["full_name"] + "/contents/examples")
        if not examples_list.ok:
            errors.append(ERROR_UNABLE_PULL_REPO_EXAMPLES)
        examples_list = examples_list.json()
        if len(examples_list) < 1:
            errors.append(ERROR_MISSING_EXAMPLE_FILES)
    else:
        errors.append(ERROR_MISSING_EXAMPLE_FOLDER)

    # first location .py files whose names begin with "adafruit_"
    re_str = re.compile('adafruit\_[\w]*\.py')
    pyfiles = [x["download_url"] for x in content_list if re_str.fullmatch(x["name"])]
    for pyfile in pyfiles:
        # adafruit_xxx.py file; check if for proper usage of ustruct
        errors.extend(validate_py_for_ustruct(repo, pyfile))

    # now location any directories whose names begin with "adafruit_"
    re_str = re.compile('adafruit\_[\w]*')
    for adir in dirs:
        if re_str.fullmatch(adir):
            # retrieve the files in that directory
            dir_file_list = github.get("/repos/" + repo["full_name"] + "/contents/" + adir)
            if not dir_file_list.ok:
                errors.append(ERROR_UNABLE_PULL_REPO_DIR)
            dir_file_list = dir_file_list.json()
            # search for .py files in that directory
            dir_files = [x["download_url"] for x in dir_file_list if x["type"] == "file" and x["name"].endswith(".py")]
            for dir_file in dir_files:
                # .py files in subdirectory adafruit_xxx; check if for proper usage of ustruct
                errors.extend(validate_py_for_ustruct(repo, dir_file))

    return errors

def validate_travis(repo):
    """Validate and configure a repository has the expected state in Travis
    CI.  This will both check Travis state and attempt to enable Travis CI
    and setup the expected state in Travis if not enabled.  Expects a
    dictionary with a GitHub API repository state (like from the list_repos
    function).  Returns a list of string error messages for the repository.
    """
    if not (repo["owner"]["login"] == "adafruit" and
            repo["name"].startswith("Adafruit_CircuitPython")):
        return []
    repo_url = "/repo/" + repo["owner"]["login"] + "%2F" + repo["name"]
    result = travis.get(repo_url)
    if not result.ok:
        #print(result, result.request.url, result.request.headers)
        #print(result.text)
        return [ERROR_TRAVIS_DOESNT_KNOW_REPO]
    result = result.json()
    if not result["active"]:
        activate = travis.post(repo_url + "/activate")
        if not activate.ok:
            print(activate.request.url)
            print(activate, activate.text)
            return [ERROR_ENABLE_TRAVIS]

    env_variables = travis.get(repo_url + "/env_vars")
    if not env_variables.ok:
        #print(env_variables, env_variables.text)
        #print(env_variables.request.headers)
        return [ERROR_TRAVIS_ENV]
    env_variables = env_variables.json()
    found_token = False
    for var in env_variables["env_vars"]:
        found_token = found_token or var["name"] == "GITHUB_TOKEN"
    ok = True
    if not found_token:
        global full_auth
        if not full_auth:
            github_user = github.get("/user").json()
            password = input("Password for " + github_user["login"] + ": ")
            full_auth = (github_user["login"], password.strip())
        if not full_auth:
            return [ERROR_TRAVIS_GITHUB_TOKEN]

        new_access_token = {"scopes": ["public_repo"],
                            "note": "TravisCI release token for " + repo["full_name"],
                            "note_url": "https://travis-ci.org/" + repo["full_name"]}
        token = github.post("/authorizations", json=new_access_token, auth=full_auth)
        if not token.ok:
            print(token.text)
            return [ERROR_TRAVIS_TOKEN_CREATE]

        token = token.json()["token"]

        new_var = {"env_var.name": "GITHUB_TOKEN",
                   "env_var.value": token,
                   "env_var.public": False}
        new_var_result = travis.post(repo_url + "/env_vars", json=new_var)
        if not new_var_result.ok:
            #print(new_var_result.headers, new_var_result.text)
            return [ERROR_TRAVIS_GITHUB_TOKEN]
    return []

def validate_readthedocs(repo):
    if not (repo["owner"]["login"] == "adafruit" and
            repo["name"].startswith("Adafruit_CircuitPython")):
        return []
    if repo["name"] in BUNDLE_IGNORE_LIST:
        return []
    global rtd_subprojects
    if not rtd_subprojects:
        rtd_response = requests.get("https://readthedocs.org/api/v2/project/74557/subprojects/")
        if not rtd_response.ok:
            return [ERROR_RTD_SUBPROJECT_FAILED]
        rtd_subprojects = {}
        for subproject in rtd_response.json()["subprojects"]:
            rtd_subprojects[sanitize_url(subproject["repo"])] = subproject

    repo_url = sanitize_url(repo["clone_url"])
    if repo_url not in rtd_subprojects:
        return [ERROR_RTD_SUBPROJECT_MISSING]

    errors = []
    subproject = rtd_subprojects[repo_url]

    if 105398 not in subproject["users"]:
        errors.append(ERROR_RTD_ADABOT_MISSING)

    valid_versions = requests.get(
        "https://readthedocs.org/api/v2/project/{}/valid_versions/".format(subproject["id"]))
    if not valid_versions.ok:
        errors.append(ERROR_RTD_VALID_VERSIONS_FAILED)
    else:
        valid_versions = valid_versions.json()
        latest_release = github.get("/repos/{}/releases/latest".format(repo["full_name"]))
        if not latest_release.ok:
            errors.append(ERROR_GITHUB_RELEASE_FAILED)
        else:
            if latest_release.json()["tag_name"] not in valid_versions["flat"]:
                errors.append(ERROR_RTD_MISSING_LATEST_RELEASE)

    # There is no API which gives access to a list of builds for a project so we parse the html
    # webpage.
    builds_webpage = requests.get(
        "https://readthedocs.org/projects/{}/builds/".format(subproject["slug"]))
    if not builds_webpage.ok:
        errors.append(ERROR_RTD_FAILED_TO_LOAD_BUILDS)
    else:
        for line in builds_webpage.text.split("\n"):
            if "<div id=\"build-" in line:
                build_id = line.split("\"")[1][len("build-"):]
            # We only validate the most recent, latest build. So, break when the first "version
            # latest" found. Its in the page after the build id.
            if "version latest" in line:
                break
        build_info = requests.get("https://readthedocs.org/api/v2/build/{}/".format(build_id))
        if not build_info.ok:
            errors.append(ERROR_RTD_FAILED_TO_LOAD_BUILD_INFO)
        else:
            build_info = build_info.json()
            output_ok = True
            autodoc_ok = True
            sphinx_ok = True
            for command in build_info["commands"]:
                if command["command"].endswith("_build/html"):
                    for line in command["output"].split("\n"):
                        if "... " in line:
                            _, line = line.split("... ")
                        if "WARNING" in line or "ERROR" in line:
                            if not line.startswith(("WARNING", "ERROR")):
                                line = line.split(" ", 1)[1]
                            if not line.startswith(RTD_IGNORE_NOTICES):
                                output_ok = False
                        elif line.startswith("ImportError"):
                            autodoc_ok = False
                        elif line.startswith("sphinx.errors") or line.startswith("SphinxError"):
                            sphinx_ok = False
                    break
            if not output_ok:
                errors.append(ERROR_RTD_OUTPUT_HAS_WARNINGS)
            if not autodoc_ok:
                errors.append(ERROR_RTD_AUTODOC_FAILED)
            if not sphinx_ok:
                errors.append(ERROR_RTD_SPHINX_FAILED)

    return errors

def validate_core_driver_page(repo):
    if not (repo["owner"]["login"] == "adafruit" and
            repo["name"].startswith("Adafruit_CircuitPython")):
        return []
    if repo["name"] in BUNDLE_IGNORE_LIST:
        return []
    global core_driver_page
    if not core_driver_page:
        driver_page = requests.get("https://raw.githubusercontent.com/adafruit/circuitpython/master/docs/drivers.rst")
        if not driver_page.ok:
            return [ERROR_DRIVERS_PAGE_DOWNLOAD_FAILED]
        core_driver_page = driver_page.text

    repo_short_name = repo["name"][len("Adafruit_CircuitPython_"):].lower()
    if "https://circuitpython.readthedocs.io/projects/" + repo_short_name + "/en/latest/" not in core_driver_page:
        return [ERROR_DRIVERS_PAGE_DOWNLOAD_MISSING_DRIVER]
    return []

def validate_repo(repo):
    """Run all the current validation functions on the provided repository and
    return their results as a list of string errors.
    """
    errors = []
    for validator in validators:
        errors.extend(validator(repo))
    return errors

def gather_insights(repo, insights, since):
    """Gather analytics about a repository like open and merged pull requests.
    This expects a dictionary with GitHub API repository state (like from the
    list_repos function) and will fill in the provided insights dictionary
    with analytics it computes for the repository.
    """
    if repo["owner"]["login"] != "adafruit":
        return
    params = {"sort": "updated",
              "state": "all",
              "since": str(since)}
    response = github.get("/repos/" + repo["full_name"] + "/issues", params=params)
    if not response.ok:
        print("request failed")
    issues = response.json()
    for issue in issues:
        created = datetime.datetime.strptime(issue["created_at"], "%Y-%m-%dT%H:%M:%SZ")
        if "pull_request" in issue:
            pr_info = github.get(issue["pull_request"]["url"])
            pr_info = pr_info.json()
            if issue["state"] == "open":
                if created > since:
                    insights["new_prs"] += 1
                    insights["pr_authors"].add(pr_info["user"]["login"])
                insights["active_prs"] += 1
            else:
                if pr_info["merged"]:
                    insights["merged_prs"] += 1
                    insights["pr_merged_authors"].add(pr_info["user"]["login"])
                    insights["pr_reviewers"].add(pr_info["merged_by"]["login"])
                else:
                    insights["closed_prs"] += 1
        else:
            issue_info = github.get(issue["url"])
            issue_info = issue_info.json()
            if issue["state"] == "open":
                if created > since:
                    insights["new_issues"] += 1
                    insights["issue_authors"].add(issue_info["user"]["login"])
                insights["active_issues"] += 1
            else:
                insights["closed_issues"] += 1
                insights["issue_closers"].add(issue_info["closed_by"]["login"])

    params = {"state": "open", "per_page": 100}
    response = github.get("/repos/" + repo["full_name"] + "/issues", params=params)
    if not response.ok:
        print("request failed")
    issues = response.json()
    for issue in issues:
        created = datetime.datetime.strptime(issue["created_at"], "%Y-%m-%dT%H:%M:%SZ")
        if "pull_request" in issue:
            insights["open_prs"].append(issue["pull_request"]["html_url"])
        else:
            insights["open_issues"].append(issue["html_url"])

def print_circuitpython_download_stats():
    """Gather and report analytics on the main CircuitPython repository."""
    response = github.get("/repos/adafruit/circuitpython/releases")
    if not response.ok:
        print("request failed")
    releases = response.json()
    found_unstable = False
    found_stable = False
    for release in releases:
        published = datetime.datetime.strptime(release["published_at"], "%Y-%m-%dT%H:%M:%SZ")
        if not found_unstable and not release["draft"] and release["prerelease"]:
            found_unstable = True
        elif not found_stable and not release["draft"] and not release["prerelease"]:
            found_stable = True
        else:
            continue

        print("Download stats for {}".format(release["tag_name"]))
        total = 0
        for asset in release["assets"]:
            if not asset["name"].startswith("adafruit-circuitpython"):
                continue
            board = asset["name"].split("-")[2]
            print("* {} - {}".format(board, asset["download_count"]))
            total += asset["download_count"]
        print("{} total".format(total))


# Define global state shared by the functions above:
# Github authentication password/token.  Used to generate new tokens.
full_auth = None
# Functions to run on repositories to validate their state.  By convention these
# return a list of string errors for the specified repository (a dictionary
# of Github API repository object state).
validators = [validate_repo_state, validate_travis, validate_contents, validate_readthedocs,
              validate_core_driver_page]
# Submodules inside the bundle (result of get_bundle_submodules)
bundle_submodules = []


if __name__ == "__main__":
    repos = list_repos()
    print("Found {} repos to check.".format(len(repos)))
    bundle_submodules = get_bundle_submodules()
    print("Found {} submodules in the bundle.".format(len(bundle_submodules)))
    github_user = github.get("/user").json()
    print("Running GitHub checks as " + github_user["login"])
    travis_user = travis.get("/user").json()
    print("Running Travis checks as " + travis_user["login"])
    need_work = 0
    insights = {
        "merged_prs": 0,
        "closed_prs": 0,
        "new_prs": 0,
        "active_prs": 0,
        "open_prs": [],
        "pr_authors": set(),
        "pr_merged_authors": set(),
        "pr_reviewers": set(),
        "closed_issues": 0,
        "new_issues": 0,
        "active_issues": 0,
        "open_issues": [],
        "issue_authors": set(),
        "issue_closers": set(),
    }
    repo_needs_work = []
    since = datetime.datetime.now() - datetime.timedelta(days=7)
    repos_by_error = {}
    for repo in repos:
        errors = validate_repo(repo)
        if errors:
            need_work += 1
            repo_needs_work.append(repo)
            # print(repo["full_name"])
            # print("\n".join(errors))
            # print()
        for error in errors:
            if error not in repos_by_error:
                repos_by_error[error] = []
            repos_by_error[error].append(repo["html_url"])
        gather_insights(repo, insights, since)
    print("State of CircuitPython + Libraries")
    print("* {} pull requests merged".format(insights["merged_prs"]))
    authors = insights["pr_merged_authors"]
    print("  * {} authors - {}".format(len(authors), ", ".join(authors)))
    reviewers = insights["pr_reviewers"]
    print("  * {} reviewers - {}".format(len(reviewers), ", ".join(reviewers)))
    new_authors = insights["pr_authors"]
    print("* {} new PRs, {} authors - {}".format(insights["new_prs"], len(new_authors), ", ".join(new_authors)))
    print("* {} closed issues by {} people, {} opened by {} people"
          .format(insights["closed_issues"], len(insights["issue_closers"]),
                  insights["new_issues"], len(insights["issue_authors"])))
    print("* {} open pull requests".format(len(insights["open_prs"])))
    for pr in insights["open_prs"]:
        print("  * {}".format(pr))
    print("* {} open issues".format(len(insights["open_issues"])))
    for issue in insights["open_issues"]:
        print("  * {}".format(issue))
    print_circuitpython_download_stats()
    # print("- [ ] [{0}](https://github.com/{1})".format(repo["name"], repo["full_name"]))
    print("{} out of {} repos need work.".format(need_work, len(repos)))

    list_repos_for_errors = [ERROR_NOT_IN_BUNDLE]

    for error in repos_by_error:
        if not repos_by_error[error]:
            continue
        print()
        error_count = len(repos_by_error[error])
        print("{} - {}".format(error, error_count))
        if error_count <= 5 or error in list_repos_for_errors:
            print("\n".join(repos_by_error[error]))
