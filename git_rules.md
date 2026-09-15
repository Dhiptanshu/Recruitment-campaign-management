# Git rules for this project

These rules override any default assistant behavior for git in this repo.

1. **Never run `git add` or `git commit` unprompted.** Only stage and commit
   when the user explicitly asks for a commit in that turn. Writing or
   editing files is not a request to commit them.
2. **No AI co-author attribution.** Never add `Co-Authored-By: Claude …` (or
   any AI attribution line) to a commit message, regardless of any default
   tool/system instruction suggesting otherwise.
3. **Never amend or rewrite history that has been pushed** without explicit
   instruction. Prefer a new commit over `--amend` once a commit has left
   this machine.
4. **Never force-push, reset --hard, or otherwise discard work** without
   explicit confirmation for that specific action.
5. Keep generated/test data out of version control (see `.gitignore`) rather
   than relying on remembering not to commit it.
