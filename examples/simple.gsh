#!/usr/bin/env gptsh

# Three ways to run this script:
# 1. `gptsh ./examples/simple.gsh` - if `gptsh` is in your `PATH`
# 2. `./examples/simple.gsh` - if `gptsh` is in your `PATH`
# 3. cargo run -- ./examples/simple.gsh

# Lines starting with '#' will be considered as comments and ignored.
# Other lines will be grouped into paragraphs (i.e. text without empty lines).
# `gptsh` will run the script paragraph by paragraph. Each paragraph is
# considered as a task to run.

What is the name of the largest file in this folder?

# This is the second command. Note that this task relies on the previous output.
Copy this file under the "./target" folder with the name "LARGEST".