# Rescribere
Rescribere is a PDF post-processing tool for parsing and editing an existing PDF file. Some codes are derived from the existing project, pyPDF, especially the filters and object parsing parts. These are modified to suit the need of the project. This project is still a work in progress.

## Roadmap
- [x] Parse the whole binary PDF file into some form of structure, including orphaned unreferenced objects.
- [ ] Write such structure back to a valid PDF file, including orphaned unreferenced objects. If the structure is not modified, the product should be functionally identical to the original file.
- [ ] Provide some intuitive way to transverse and modify the structure in Python (alpha stage)
- [ ] Provide a GUI for viewing and editing the structure (beta to release stage)
- [ ] May be a single page live preview? (release stage)
- [ ] Implment PDF encryption