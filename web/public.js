(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('public-data').textContent);
  const el = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
  const number = new Intl.NumberFormat('es-MX', {maximumFractionDigits:0});
  const decimal = new Intl.NumberFormat('es-MX', {minimumFractionDigits:1,maximumFractionDigits:1});
  const normalize = text => String(text).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const geography = new Map(data.geometry.features.map(feature => [feature.properties.code, feature.properties]));
  const maps = {};
  const selections = {};
  const latest = data.periods.at(-1).id;
  const options = data.periods.map(period => `<option value="${period.id}">${period.label}</option>`).join('');
  const metricOptions = data.metrics.map(metric => `<option value="${metric.id}">${escape(metric.title)}</option>`).join('');
  const colors = ['#ffffcc','#ffeda0','#fed976','#feb24c','#fd8d3c','#fc4e2a','#e31a1c','#b10026'];
  const table = {metric:'total',period:latest,query:'',sort:'code',direction:1,page:1};
  const pageSize = 12;
  const released = cells => cells.filter(cell => !cell.suppressed);
  const sum = cells => cells.reduce((total,cell) => total + cell.count,0);
  const maxRate = cells => Math.max(0,...cells.map(cell => cell.rate ?? 0));
  const color = (value,maximum) => value === null ? '#dce1d9' : colors[Math.min(colors.length-1,maximum > 0 ? Math.floor(Math.max(0,value)/maximum*colors.length) : 0)];

  el('hero-years').textContent = `${data.min_year}–${data.max_year}`;
  el('coverage-agebs').textContent = data.census_agebs;
  el('coverage-positive').textContent = data.positive_population_agebs;
  el('maps-container').innerHTML = data.metrics.map((metric,index) => `<article class="map-card" id="panel-${metric.id}" aria-labelledby="heading-${metric.id}"><div class="map-card-head"><div class="map-title"><span class="map-number">0${index+1}</span><div><h3 id="heading-${metric.id}">${escape(metric.title)}</h3><p>${escape(metric.description)}</p></div></div><label class="map-period" for="period-${metric.id}">Periodo<select id="period-${metric.id}" aria-controls="map-${metric.id} stats-${metric.id}">${options}</select></label></div><div class="map-stats" id="stats-${metric.id}" role="group" aria-label="Resultados publicados del mapa" aria-live="polite"><div class="map-stat"><span>Casos publicados</span><strong id="count-${metric.id}">—</strong><small>Suma de celdas redondeadas</small></div><div class="map-stat"><span>AGEB publicables</span><strong id="agebs-${metric.id}">—</strong><small>De ${data.census_agebs} áreas estudiadas</small></div><div class="map-stat"><span>Tasa máxima aproximada</span><strong id="rate-${metric.id}">—</strong><small>Por 100,000 habitantes</small></div></div><div class="public-map" id="map-${metric.id}" role="region" aria-label="Mapa de ${escape(metric.title)} por AGEB"></div><div class="map-legend"><span>0</span><span class="color-scale" aria-hidden="true"></span><span id="legend-${metric.id}">—</span><span>por 100,000</span><span class="legend-protection"><span class="suppressed-key" aria-hidden="true"></span>Protegido o sin denominador</span></div></article>`).join('');

  function updateMap(metric) {
    const period = el('period-'+metric).value;
    selections[metric] = period;
    const cells = data.cells[metric][period];
    const lookup = new Map(cells.map(cell => [cell.code,cell]));
    const published = released(cells);
    const maximum = maxRate(cells);
    const map = maps[metric];
    map.layer.eachLayer(layer => {
      const info = layer.feature.properties;
      const cell = lookup.get(info.code);
      layer.setStyle({fillColor:color(cell.rate,maximum),fillOpacity:.78,weight:.7,color:'#80947e'});
      const amount = cell.suppressed ? 'Protegido (&lt;5, incluido cero)' : `≈ ${number.format(cell.count)}`;
      const rate = cell.suppressed ? 'Protegida' : cell.rate === null ? 'Sin denominador positivo' : `≈ ${decimal.format(cell.rate)} por 100,000`;
      layer.bindPopup(`<h4>AGEB ${escape(info.ageb)}</h4><div>${escape(info.municipality)} · ${period.replace('-','–')}</div><div class="popup-score">${amount}</div><div>Casos publicados · ${escape(data.metrics.find(item=>item.id===metric).title)}</div><hr><div><strong>Tasa:</strong> ${rate}</div><div><strong>Población censal:</strong> ${number.format(info.population)}</div><small>Conteos suprimidos o redondeados; no contiene fichas de pacientes.</small>`);
      layer.bindTooltip(`AGEB ${escape(info.ageb)} · ${cell.suppressed ? 'Resultado protegido' : `≈ ${number.format(cell.count)} casos publicados`}`);
    });
    el('count-'+metric).textContent = published.length ? '≈ '+number.format(sum(published)) : '—';
    el('agebs-'+metric).textContent = number.format(published.length);
    el('rate-'+metric).textContent = published.some(cell=>cell.rate!==null) ? '≈ '+decimal.format(maximum) : '—';
    el('legend-'+metric).textContent = decimal.format(maximum);
  }

  for (const metric of data.metrics) {
    el('period-'+metric.id).value = latest;
    const map = L.map('map-'+metric.id,{scrollWheelZoom:false,preferCanvas:true});
    map.attributionControl.setPrefix(false);
    map.attributionControl.addAttribution('AGEB · Censo 2020 | Leaflet');
    const status = document.createElement('p');
    status.className = 'basemap-status';
    status.setAttribute('role', 'status');
    status.hidden = true;
    status.textContent = 'No se pudo cargar el mapa base de CARTO. Puedes seguir explorando las áreas y sus resultados.';
    map.getContainer().after(status);
    const basemap = L.tileLayer('https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
      maxZoom: 20,
      referrerPolicy: 'no-referrer'
    });
    basemap.on('tileerror', () => { status.hidden = false; });
    basemap.on('tileload', () => { status.hidden = true; });
    basemap.addTo(map);
    const layer = L.geoJSON(data.geometry).addTo(map);
    map.fitBounds(layer.getBounds(),{padding:[15,15],animate:false});
    maps[metric.id] = {map,layer,basemap};
    el('period-'+metric.id).addEventListener('change',()=>updateMap(metric.id));
    new ResizeObserver(()=>{map.invalidateSize({animate:false});map.fitBounds(layer.getBounds(),{padding:[15,15],animate:false});}).observe(el('map-'+metric.id));
    updateMap(metric.id);
  }

  function updateTrend() {
    const metric = el('trend-metric').value;
    const values = data.periods.map(period=>({label:period.label,value:sum(released(data.cells[metric][period.id])),available:released(data.cells[metric][period.id]).length>0}));
    const width=1000,height=220,left=25,bottom=36,top=30,max=Math.max(1,...values.map(item=>item.value));
    const step=(width-left-15)/values.length;
    const baseline=height-bottom;
    const bars=values.map((item,index)=>{
      const x=left+index*step+step*.18;
      const barWidth=step*.64;
      const barHeight=item.value/max*(height-bottom-top);
      return `<rect x="${x}" y="${baseline-barHeight}" width="${barWidth}" height="${barHeight}" rx="3" fill="${index===values.length-1?'#275e41':'#a7be84'}"/><text class="bar-value" x="${x+barWidth/2}" y="${baseline-barHeight-9}" text-anchor="middle">${item.available?'≈'+number.format(item.value):'—'}</text><text x="${x+barWidth/2}" y="${height-14}" text-anchor="middle">${item.label}</text>`;
    }).join('');
    el('public-trend').innerHTML = `<svg viewBox="0 0 ${width} ${height}" aria-hidden="true"><line x1="${left}" x2="${width-15}" y1="${baseline}" y2="${baseline}" stroke="#dce4d2"/>${bars}</svg>`;
    el('public-trend').setAttribute('aria-label',data.metrics.find(item=>item.id===metric).title+': '+values.map(item=>`${item.label}: ${item.available?'aproximadamente '+number.format(item.value)+' casos publicados':'sin celdas publicables'}`).join('; '));
  }
  el('trend-metric').innerHTML=metricOptions;
  el('trend-metric').addEventListener('change',updateTrend);
  updateTrend();

  function tableRows() {
    return data.cells[table.metric][table.period].map(cell=>({...geography.get(cell.code),...cell})).filter(row=>normalize(row.code+' '+row.ageb+' '+row.municipality).includes(normalize(table.query))).sort((a,b)=>{
      const first=a[table.sort],second=b[table.sort];
      if(first===null&&second!==null)return 1;
      if(second===null&&first!==null)return -1;
      if(first===null&&second===null)return a.code.localeCompare(b.code);
      return table.direction*(typeof first==='number'?first-second:String(first).localeCompare(String(second),'es'))||a.code.localeCompare(b.code);
    });
  }

  function updateTable() {
    const rows=tableRows();
    const pages=Math.max(1,Math.ceil(rows.length/pageSize));
    table.page=Math.min(table.page,pages);
    const start=(table.page-1)*pageSize;
    el('public-table').innerHTML=rows.length?rows.slice(start,start+pageSize).map(row=>`<tr><td><strong>${escape(row.ageb)}</strong><br><small>${row.code}</small></td><td>${escape(row.municipality)}</td><td>${number.format(row.population)}</td><td class="${row.suppressed?'protected-cell':''}">${row.suppressed?'Protegido (&lt;5)':'≈ '+number.format(row.count)}</td><td class="${row.rate===null?'protected-cell':''}">${row.suppressed?'Protegida':row.rate===null?'Sin denominador':'≈ '+decimal.format(row.rate)}</td></tr>`).join(''):'<tr><td colspan="5" class="empty">No se encontraron AGEB con esa búsqueda.</td></tr>';
    el('table-status').textContent=rows.length?`${start+1}–${Math.min(start+pageSize,rows.length)} de ${rows.length} AGEB`:'0 AGEB';
    el('page-status').textContent=`${table.page} / ${pages}`;
    el('prev-page').disabled=table.page<=1;
    el('next-page').disabled=table.page>=pages;
    el('download-csv').disabled=!rows.length;
    document.querySelectorAll('[data-sort]').forEach(button=>button.parentElement.setAttribute('aria-sort',button.dataset.sort===table.sort?table.direction===1?'ascending':'descending':'none'));
  }
  el('table-metric').innerHTML=metricOptions;
  el('table-period').innerHTML=options;
  el('table-period').value=latest;
  el('table-metric').addEventListener('change',event=>{table.metric=event.target.value;table.page=1;updateTable();});
  el('table-period').addEventListener('change',event=>{table.period=event.target.value;table.page=1;updateTable();});
  el('table-search').addEventListener('input',event=>{table.query=event.target.value;table.page=1;updateTable();});
  document.querySelectorAll('[data-sort]').forEach(button=>button.addEventListener('click',()=>{table.direction=table.sort===button.dataset.sort?-table.direction:1;table.sort=button.dataset.sort;table.page=1;updateTable();}));
  el('prev-page').addEventListener('click',()=>{table.page--;updateTable();});
  el('next-page').addEventListener('click',()=>{table.page++;updateTable();});
  el('download-csv').addEventListener('click',()=>{
    const cell=value=>'"'+String(value??'').replace(/"/g,'""')+'"';
    const headers=['clave_ageb','municipio','periodo','indicador','poblacion_2020','casos_publicados','tasa_aproximada','protegido'];
    const rows=tableRows().map(row=>[row.code,row.municipality,table.period,table.metric,row.population,row.suppressed?'Protegido (<5)':row.count,row.suppressed?'Protegida':row.rate===null?'Sin denominador':row.rate,row.suppressed?'sí':'no']);
    const url=URL.createObjectURL(new Blob(['\uFEFF'+[headers,...rows].map(row=>row.map(cell).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}));
    const anchor=document.createElement('a');anchor.href=url;anchor.download=`RERIMSS-publico-${table.metric}-${table.period}.csv`;document.body.append(anchor);anchor.click();anchor.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  el('print-public').addEventListener('click',()=>window.print());
  updateTable();
  // Solo estado y resultados públicos; útil para validar las capas del navegador.
  window.RERIMSS_PUBLIC={maps,selections};
})();
