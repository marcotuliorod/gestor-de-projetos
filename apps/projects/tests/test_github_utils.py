from django.test import SimpleTestCase

from apps.projects.github_utils import parse_github_repo_url


class ParseGithubRepoUrlTests(SimpleTestCase):
    def test_plain_url(self):
        self.assertEqual(parse_github_repo_url("https://github.com/ju/api-financeiro"), ("ju", "api-financeiro"))

    def test_git_suffix(self):
        self.assertEqual(parse_github_repo_url("https://github.com/ju/api-financeiro.git"), ("ju", "api-financeiro"))

    def test_trailing_slash(self):
        self.assertEqual(parse_github_repo_url("https://github.com/ju/api-financeiro/"), ("ju", "api-financeiro"))

    def test_without_scheme(self):
        self.assertEqual(parse_github_repo_url("github.com/ju/api-financeiro"), ("ju", "api-financeiro"))

    def test_www(self):
        self.assertEqual(parse_github_repo_url("https://www.github.com/ju/api-financeiro"), ("ju", "api-financeiro"))

    def test_empty(self):
        self.assertIsNone(parse_github_repo_url(""))

    def test_not_github(self):
        self.assertIsNone(parse_github_repo_url("https://gitlab.com/ju/api-financeiro"))

    def test_invalid(self):
        self.assertIsNone(parse_github_repo_url("not a url"))
