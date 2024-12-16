# Design Document: Metadata validation

## Introduction

### Component Overview and Scope

SoilWise Repository aims for the approach to harvest and register as much as possible. Catalogues which capture metadata authored by data custodians typically have a wide range of metadata completion and accuracy. Therefore, the SoilWise Repository employs metadata validation mechanisms to provide additional information about metadata completeness, conformance and integrity. Information resulting from the validation process are stored together with each metadata record in a relation database and updated after registering a new metadata version.

### Users

1. **authorised data users**
    - see validation results (log) per each metadata record

2. **unauthorised data users**
3. **administrators**
    - manually run validation
    - see summary validation results
    - monitor validation process

### References

- [INSPIRE validator](https://inspire.ec.europa.eu/validator/home/index.html)

## Requirements

### Functional Requirements

- provide means for validation of data, metadata and web services, knowledge?
- provide additional information about metadata completeness, conformance and integrity
- perform validation against INSPIRE metadata profile
- validate the level of data duplication from remote sources
- automated? regular validation at least once per six months after the first project year

### Non-functional Requirements

- follow ATS ETS approach and implement AI / ML enrichment
- reach TRL 7
- adopt the ISO 19157 data quality measures
- JRC does not want to discourage data providers from publishing metadata by visualizing, that they are not conformant with a set of rules

## Architecture

### Technological Stack

- [Hale Studio](https://wetransform.to/halestudio/)

### Overview of Key Features

1. [Link Liveliness Assessment](/link-liveliness-assessment/blob/main/docs/design.md): to validate if the reference link is currently working, or deprecated. This is a separate component, which returns a http status: `200 OK`, `401 Non Authorized`, `404 Not Found`, `500 Server Error` and timestamp.


### Component Diagrams

### Sequence Diagram

### Database Design

### Integrations & Interfaces

- in the first iteration, validation component is not integrated
- [Link Liveliness Assessment](/link-liveliness-assessment/blob/main/docs/design.md) is considered a part of metadata validation process
- Harvester
- Catalogue
- Storage

### Key Architectural Decisions

- for the first iteration, Hale Studio was selected, with restricted access to the validation results
- Shacl validation was discussed to be implemented for next iterations
- minimal SoilWise profile was discussed to indicate compliance with SoilWise functionality
- EUSO Metadata profile was discussed 
- two-step validation of metadata was discussed, at first using harvested metadata, and next using SoilWise-augmented metadata

## Risks & Limitations

- Hale Studio currently does not support Dublin Core
