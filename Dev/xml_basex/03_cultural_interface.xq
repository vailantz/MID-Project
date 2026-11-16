(: Interface do adaptador: elementos do XML passam a tuplos com campos explicitos.
   Os dados culturais continuam na sua fonte; nao sao tabelas PostgreSQL. :)
<places>{
  for $p in /culturalCatalogue/place
  order by string($p/@id)
  return <place id="{string($p/@id)}" category="{string($p/@category)}">
    <name>{normalize-space($p/name)}</name>
    <latitude>{normalize-space($p/location/latitude)}</latitude>
    <longitude>{normalize-space($p/location/longitude)}</longitude>
  </place>
}</places>
