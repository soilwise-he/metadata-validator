# Abstract test Suite - Metadeta template

The elements below are suggested on being available in the suggested cardinality and type.

| Element DC | Element ISO | Cardinality | Type | Codelist | Comment |
| --- | --- | --- | --- | --- | --- |
| [identifier](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#identifier) | fileidentifier | 1-n | string | - | |
| [title](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#title) | title | 1-n | string | - | |
| [language](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#language) | language | 0-n | string | - | 2/3/5-letter iso? |
| [description](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#description) | abstract | 0-n | string | | |
| [created](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#created) | date@creation | 0-n | date | | |
| [issued](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#issued) | date@published | 0-n | date | | |
| relation | distributioninfo | 0-n | str or uri | | Dublin Core has limited options to reference the resource it describes | 
| [creator](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#creator) | contact#author | 0-n | str or uri | | | 
| [publisher](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#publisher) | contact#distributor | 0-n | str or uri | | | 
| [temporal](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#temporal) | extent#temporal | 0-n | date-period | | | 
| [spatial](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#spatial) | extent#spatial | 0-n | str, uri or bbox | | | 
| [rights](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#right) | otherconstraints | 0-1 | str or uri | | | 
| [license](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#license)  | otherconstraints | 0-1 | str or uri | | | 
| [conformsTo](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#conformsTo) | DQ_DomainConsistency/DQ_ConformanceResult | 0-1 | str or uri | | | 
| [subject](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#subject)  | keyword/topiccategory | 0-n | str or uri | | | 
| [type](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#type)  | hierarchylevel | 1-1 | str or uri | | | 
| [format](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#format)  | format | 0-1 | str or uri | | | 

