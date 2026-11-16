declare namespace xsi = 'http://www.w3.org/2001/XMLSchema-instance';
let $places := /culturalCatalogue/place
return <quality
  places="{count($places)}"
  duplicateIds="{count($places) - count(distinct-values($places/@id))}"
  missingNames="{count($places[not(normalize-space(name))])}"
  unknownCategories="{count($places[not(@category = ('museum','monument'))])}"
  missingSourceReferences="{count($places[not(@sourceRef = /culturalCatalogue/sources/source/@id)])}">
  {
    for $p in $places
    let $lat := $p/location/latitude
    let $lon := $p/location/longitude
    where not($lat castable as xs:decimal) or not($lon castable as xs:decimal)
    return <missingCoordinates id="{string($p/@id)}"/>
  }
</quality>
