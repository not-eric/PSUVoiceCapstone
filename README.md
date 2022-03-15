# Portland State University Computer Science Capstone <br>Fall-Winter 2021

Repository for the PSU capstone project,
the _Voice-based Privacy Policy Consent System_,
sponsored by the Open Voice Network.
The final project reflection video
[can be viewed here](https://www.youtube.com/watch?v=MWVJA5ly7os).

User and system documentation can be found in the `docs` folder, along with
a document describing some of the design decisions and challenges we ran into
as a team over the course of the project.

## Installation

To import _only_ the lambda code into the Alexa Skills Kit (ASK),
[follow this guide](https://developer.amazon.com/en-US/docs/alexa/hosted-skills/alexa-hosted-skills-create.html#import-code) using the folders found in `src`.

Currently, the process of installing the entire skill (both the lambda _and_ the
interaction model) is a bit convoluted: the desired source folder must be copied
into its own public Git repository, and then imported
[following this guide](https://developer.amazon.com/en-US/docs/alexa/hosted-skills/alexa-hosted-skills-git-import.html).
