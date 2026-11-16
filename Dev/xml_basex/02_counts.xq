<counts>{
  for $category in distinct-values(/culturalCatalogue/place/@category)
  order by $category
  return <category name="{$category}" count="{count(/culturalCatalogue/place[@category = $category])}"/>
}</counts>
