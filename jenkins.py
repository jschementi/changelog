import requests
from xml.etree import ElementTree

jenkins_auth = (None, None)
jenkins_url = None

def set_config(url, username, password):
    global jenkins_auth
    global jenkins_url
    if username is not None and password is not None:
        jenkins_auth = (username, password)
    if url is not None:
        jenkins_url = url

def get_ci_job_url(job_name):
    return '%s/job/%s/api/json' % (jenkins_url, job_name)

def get_ci_build_url(job_name, build_number):
    return '%s/job/%s/%s/api/json' % (jenkins_url, job_name, build_number)

def get_ci_job(job_name):
    r = requests.get(get_ci_job_url(job_name), auth=jenkins_auth)
    r.raise_for_status()
    return r.json()

def get_ci_build(job_name, build_number):
    r = requests.get(get_ci_build_url(job_name, build_number), auth=jenkins_auth)
    r.raise_for_status()
    return r.json()

def get_ci_job_config(job_name):
    r = requests.get('%s/job/%s/config.xml' % (jenkins_url, job_name), auth=jenkins_auth)
    r.raise_for_status()
    return ElementTree.fromstring(r.text)

def get_ci_job_repo_url(job_name):
    tree = get_ci_job_config(job_name)
    return tree.find('./scm/userRemoteConfigs/hudson.plugins.git.UserRemoteConfig/url').text.strip()

def get_build_numbers(job_name):
    return [build['number'] for build in get_ci_job(job_name)['builds']]
