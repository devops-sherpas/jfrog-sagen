# Cloud Migration Utilities

## Preparation

1. Create a Python virtual environment and activate it.
2. Install requirements:

   ```bash
   pip install -r requirements.txt
   ```

## Artifactory Sites Diff

```bash
python artifactory/sites_diff.py --help
```

## Xray Reports

### Exporting Definitions

```bash
python xray/reports.py export-definitions --help
```

### Exporting Contents

```bash
python xray/reports.py export-contents --help
```

### Importing Definitions

```bash
python xray/reports.py import-definitions --help
```
