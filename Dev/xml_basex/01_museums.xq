(: Abrir a base cultural no BaseX, ou usar -i com o XML. :)
<museums>{
  for $p in /culturalCatalogue/place[@category = 'museum']
  order by normalize-space($p/name)
  return <museum id="{string($p/@id)}">{normalize-space($p/name)}</museum>
}</museums>
