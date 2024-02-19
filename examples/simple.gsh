#!/usr/bin/env gptsh

# Usage: `gptsh ./examples/simple.gsh`

# Lines starting with '#' will be considered as comments and ignored.
# Other lines will be grouped into paragraphs (i.e. text without empty lines).
# `gptsh` will run the script paragraph by paragraph. Each paragraph is
# considered as a task to run.

List all the files with size under current dir. Exclude directories, and files in subfolders.

From the previous output, which file has the largest size?

Copy this file under the "./target" folder with the name "LARGEST".