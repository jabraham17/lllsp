# Developer Docs

## Publishing


1 .Update the version number. Make sure to commit and push this change

2. Run the following commands
```
# Optionally
npx vsce login ....
# Build the extension
npx vsce package
# Publish the extension
npx vsce publish
```

3. Make sure to then generate a release on GitHub with the same version number as the one in `package.json`.
