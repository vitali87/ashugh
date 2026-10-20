# Notices

## Russian stress table

`src/ashugh/data/ru_stress.tsv` is derived from the OpenRussian dictionary
data (<https://en.openrussian.org>, published at
<https://github.com/Badestrand/russian-dictionary>), © the OpenRussian team
and contributors, which in turn draws on Wiktionary. It is licensed under the
Creative Commons Attribution-ShareAlike 4.0 International license
(<https://creativecommons.org/licenses/by-sa/4.0/>).

Changes: inflected forms were extracted from nouns.csv, verbs.csv,
adjectives.csv and others.csv, lowercased, and reduced to the positions of
their stressed vowels by `scripts/build_ru_lexicon.py`. The derived table is
distributed under the same CC BY-SA 4.0 license. The rest of ashugh is MIT
licensed (see LICENSE).
