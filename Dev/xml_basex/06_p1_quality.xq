declare namespace xsi = 'http://www.w3.org/2001/XMLSchema-instance';

let $places := /culturalCatalogue/place
return <quality places="{count($places)}"
  categorySourceMismatches="{count($places[@category != @sourceRef])}"
  idPrefixMismatches="{count($places[not(starts-with(string(@id), concat(string(@category), ':')))])}"
  invalidNilValues="{count($places//*[(@xsi:nil = ('true', '1')) and normalize-space(.) != ''])}">
  <fields>{
    for $field in ('telephone', 'fax', 'email', 'website', 'description')
    let $nodes := if ($field = 'description') then $places/description
                  else $places/contact/*[local-name() = $field]
    let $notNil := $nodes[not(@xsi:nil = ('true', '1'))]
    return <field name="{$field}" missing="{count($places) - count($nodes)}"
      nil="{count($nodes[@xsi:nil = ('true', '1')])}"
      blank="{count($notNil[normalize-space(.) = ''])}"
      placeholder="{count($notNil[normalize-space(.) = '-'])}"
      usable="{count($notNil[not(normalize-space(.) = ('', '-'))])}"/>
  }</fields>
  <repeatedNames>{
    for $name in distinct-values($places/name/normalize-space(.))
    let $matches := $places[normalize-space(name) = $name]
    where count($matches) > 1
    order by $name
    return <name value="{$name}" records="{count($matches)}">{
      for $place in $matches order by string($place/@id)
      return <place id="{string($place/@id)}" category="{string($place/@category)}"/>
    }</name>
  }</repeatedNames>
</quality>
