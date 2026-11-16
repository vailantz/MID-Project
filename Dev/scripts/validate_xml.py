"""Valida a estrutura comum do XML do projeto e demonstra rejeicoes pelo XSD."""
from pathlib import Path
import argparse
import copy
import json
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xml', type=Path, default=ROOT/'data/cultural_catalogue.xml')
    parser.add_argument('--xsd', type=Path, default=ROOT/'xml_basex/catalogue.xsd')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    safe = etree.XMLParser(resolve_entities=False, no_network=True)
    doc = etree.parse(str(args.xml), safe)
    schema = etree.XMLSchema(etree.parse(str(args.xsd), safe))
    schema.assertValid(doc)
    checks = ['original_catalogue_valid']
    if args.self_test:
        cases = []
        altered = copy.deepcopy(doc); p = altered.getroot().find('place'); p.remove(p.find('name'))
        cases.append(('missing_name_rejected', altered))
        altered = copy.deepcopy(doc); altered.getroot().find('place/location/latitude').text='95'
        cases.append(('latitude_out_of_range_rejected', altered))
        altered = copy.deepcopy(doc); ps=altered.getroot().findall('place'); ps[1].set('id',ps[0].get('id'))
        cases.append(('duplicate_place_id_rejected', altered))
        altered = copy.deepcopy(doc); altered.getroot().find('place').set('sourceRef','unknown')
        cases.append(('unknown_source_rejected', altered))
        for name, altered in cases:
            if schema.validate(altered):
                raise AssertionError(name)
            checks.append(name)
    report = {'status':'passed','xml_records':len(doc.getroot().findall('place')),
              'checks_passed':len(checks),'checks':checks,
              'scope':'Project XSD 1.0: common structure, types, coordinate bounds, keys and source references',
              'limits':['Raw sourceFields are preserved without field-specific validation',
                        'Schema validation does not establish the real-world truth or freshness of values']}
    output = ROOT/'results/xml_schema_validation.json'
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
