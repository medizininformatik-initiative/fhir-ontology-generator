# Development

## Release Checklist

 > [!NOTE]
 > This guide uses a fairly explicit set of **git** commands for clarity. Feel free to adapt them to suit your preference

1. Create a release branch from protected branch `main`:

    ````bash
    git checkout main
    git branch <branch-name>
    git checkout <branch-name>
    ````
    The branch name `branch-name` should adhere to the pattern `release-<version-tag-name>` where the `version-tag-name` is the name of tag that applied to the release state of the repository. 
2. Update the `CHANGELOG.md` file by adding a new entry for the version (and likely milestone), documenting the introduced changes. Afterwards commit the update to the file and push the release branch to the remote repository.
3. Create a **pull request** from the **release branch** (e.g. `<branch-name>`) into the protected `main` branch.
4. Merge the pull request after approval was given.
5. Fetch the new state of the `main` branch from the remote to your local repository:
    ```bash
    git checkout main
    git pull <remote> main
    ```
    or
    ```bash
    git fetch
    git checkout main
    ```
    Next, tag that state with an appropriately named tag `v<major>.<minor>.<path>[-<optional-details>]` and push the tag to the remote repository:   
    ````bash
    git tag -a <release-tag-name> -m "Short release description"
    git push <remote> tag <release-tag-name>
    ````
   Afterwards confirm that the CI/CD pipeline is running and is not skipping the `release` step. 
6. Once released, edit the release notes if necessary such that they adhere to the schema of previous releases

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