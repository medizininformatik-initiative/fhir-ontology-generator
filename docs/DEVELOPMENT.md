# Development

## Release Checklist

* create a release branch called `release-v<version>` like `release-v0.1.1`
* update the CHANGELOG based on the milestone
* create a commit with the title `Release v<version>`
* create a PR from the release branch into main
* merge that PR
* create and push a tag called `v<version>` like `v0.1.1` on main at the merge commit
* create release and release notes on GitHub linking the appropriate tag

## Recommended Setup For Local Testing

While the FDPG team provides an all-encompassing repository in 
[feasibility-develop](https://github.com/medizininformatik-initiative/feasibility-develop) to launch all the required 
software components for a standalone feasibility triangle, developers might find this setup restrictive since access to 
individual components is limited by the extensive use of docker containers. For instance, if testing CQL query 
translation in the backend component, being able to launch the application in debug mode in your IDE of choice might 
make this task significantly easier. For this reason it is recommended to launch components from their respective 
repositories to have insight into the codebase and allow for better debug access. How this can be done will be 
explained in this section.

### 1. Download Individual Repositories

Clone the [feasibility-auth](https://github.com/medizininformatik-initiative/feasibility-auth), 
[feasibility-backend](https://github.com/medizininformatik-initiative/feasibility-backend), and 
[feasibility-gui](https://github.com/medizininformatik-initiative/feasibility-gui) repositories from the 
[**medizininformatik-initiative**](https://github.com/medizininformatik-initiative) organization on GitHub. Check out 
the respective **development** (e.g. `dev`, `develop`, etc.) branches on each local version of the repositories.

### 2. Setup and Deploy `feasibility-auth`



### 3. Setup and Deploy `feasbility-gui`



### 4. Generate Ontologies



### 5. Setup and Deploy `feasibility-backend`