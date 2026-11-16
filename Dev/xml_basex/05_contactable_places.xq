declare namespace xsi = 'http://www.w3.org/2001/XMLSchema-instance';

declare function local:usable($field as element()?) as xs:boolean {
  exists($field)
  and not($field/@xsi:nil = ('true', '1'))
  and not(normalize-space($field) = ('', '-'))
};

<contactablePlaces>{
  for $place in /culturalCatalogue/place
  let $source := /culturalCatalogue/sources/source[@id = $place/@sourceRef]
  let $contacts := $place/contact/*[local-name() = ('telephone', 'email', 'website')][local:usable(.)]
  where exists($contacts) and local:usable($place/description)
  order by string($place/@category), normalize-space($place/name), string($place/@id)
  return <place id="{string($place/@id)}" category="{string($place/@category)}" sourceRef="{string($source/@id)}">
    <name>{normalize-space($place/name)}</name>
    <contacts>{
      for $contact in $contacts
      return element {node-name($contact)} {normalize-space($contact)}
    }</contacts>
    <description>{normalize-space($place/description)}</description>
    <provenance provider="{string($source/@provider)}" accessDate="{string($source/@accessDate)}">
      <catalogueUrl>{string($source/catalogueUrl)}</catalogueUrl>
    </provenance>
  </place>
}</contactablePlaces>
