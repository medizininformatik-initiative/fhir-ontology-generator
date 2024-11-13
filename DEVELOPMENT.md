# Development

## Release Checklist

* create a release branch called `release-v<version>` like `release-v0.1.1`
* update the CHANGELOG based on the milestone
* create a commit with the title `Release v<version>`
* create a PR from the release branch into main
* merge that PR
* create and push a tag called `v<version>` like `v0.1.1` on main at the merge commit
* create release and release notes on GitHub linking the appropriate tag