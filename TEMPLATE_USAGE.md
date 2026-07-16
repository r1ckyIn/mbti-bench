# How to Use This Template

## Method 1: Use GitHub Template (Recommended)

1. Go to https://github.com/r1ckyIn/project-template
2. Click the green **"Use this template"** button
3. Select **"Create a new repository"**
4. Fill in your new repository name and description
5. Click **"Create repository"**
6. Clone your new repository and start coding!

## Method 2: Manual Clone

```bash
# Clone the template
git clone https://github.com/r1ckyIn/project-template.git my-new-project
cd my-new-project

# Remove the template's git history
rm -rf .git

# Initialize a fresh git repository
git init
git add .
git commit -m "Initial commit from template"

# Add your new remote
git remote add origin git@github.com:r1ckyIn/my-new-project.git
git push -u origin main
```

## After Creating Your Project

### 1. Update README.md

- [ ] Change "Project Name" to your actual project name
- [ ] Update the one-line description
- [ ] Choose appropriate badges (uncomment/delete as needed)
- [ ] Update clone URL to your repository
- [ ] Fill in Features section
- [ ] Update Project Structure
- [ ] Update Tech Stack

### 2. Update Other Files

- [ ] Update `requirements.txt` with your dependencies
- [ ] Modify `.gitignore` if needed for your project type

### 3. Add Topics to Your Repository

Use GitHub CLI to add topics:

```bash
gh repo edit r1ckyIn/your-repo-name --add-topic python,your-topic,usyd
```

### Suggested Topics by Project Type

| Project Type | Suggested Topics |
|--------------|------------------|
| Python OOP | `python`, `oop`, `usyd` |
| Java OOP | `java`, `oop`, `usyd`, `info1113` |
| Web App | `javascript`, `react`, `nodejs`, `usyd` |
| Cloud/AWS | `python`, `aws`, `cloud-computing`, `usyd` |
| MCP Server | `python`, `mcp`, `claude`, `usyd` |
| Data Science | `python`, `data-science`, `machine-learning`, `usyd` |

## Badge Reference

### Language Badges

```markdown
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Java](https://img.shields.io/badge/Java-17+-ED8B00?style=flat-square&logo=openjdk&logoColor=white)](https://openjdk.org)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES6+-F7DF1E?style=flat-square&logo=javascript&logoColor=black)](https://developer.mozilla.org/en-US/docs/Web/JavaScript)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
```

### Framework/Tool Badges

```markdown
[![React](https://img.shields.io/badge/React-18+-61DAFB?style=flat-square&logo=react&logoColor=black)](https://reactjs.org)
[![Node.js](https://img.shields.io/badge/Node.js-18+-339933?style=flat-square&logo=nodedotjs&logoColor=white)](https://nodejs.org)
[![AWS](https://img.shields.io/badge/AWS-Cloud-FF9900?style=flat-square&logo=amazon-aws&logoColor=white)](https://aws.amazon.com)
[![Docker](https://img.shields.io/badge/Docker-24+-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com)
[![MCP](https://img.shields.io/badge/MCP-Server-FF6B35?style=flat-square)](https://modelcontextprotocol.io)
```

### Standard Badges

```markdown
[![USYD](https://img.shields.io/badge/USYD-CS-00205B?style=flat-square)](https://www.sydney.edu.au/)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen?style=flat-square)](http://makeapullrequest.com)
```
