# python-template
Template repo for Python projects.

## How to Use
This template should be used whenever you are starting a new Python project and allows you, the developer, to focus on your project and not all of the extra setup. To use, when you are creating your repo for your new project, select this repo when GitHub asks if you want to use a template repo. This project assumes the use of [Poetry](https://python-poetry.org).

## What's in the Box?
- GitHub Action to run Pytest
- A Codeowners file that you will need to update with your teams Github handle.
- Pre-Commit hook to run black, isort, and flake8.
- Configuration files for [flake8](/.flake8) and [isort](/.isort.cfg).
- A .gitignore file configured for Python and Terraform.
- A [pyproject.toml](/pyproject.toml) file that you will need to edit with your projects information and requirements.
- A `src` directory for your python code.
- A `tests` directory for your tests.

## Installing the Pre-Commit Hook
Set it up once and you won't have to think about it again!

```bash
#(optional, set up python env)
python3 -m venv ./.venv
source ./.venv/bin/activate

# locally in your virtual environment for this project
# (the way to go if you don't want to use poetry globally and only for this project)
python3 -m pip install poetry

# OR globally
curl -sSL https://install.python-poetry.org | python3 -

# install dependencies
poetry install

# execute pre-commit install to install git hooks in your .git/ directory
# this will allow linting and formatting on commit
pre-commit install
```
