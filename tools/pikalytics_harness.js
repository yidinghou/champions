// Re-derive damage_cases.json expectations from Pikalytics (source of truth for damage).
// Usage: open https://www.pikalytics.com/damage-calculator (Champions ruleset is the default), run this in
// the page (browser console, or Playwright browser_evaluate as `() => { ...body... }`), then copy each result's
// `rolls` into data/damage_cases.json as {"expected": [min, max], "rolls": [...]}.
//
// Gotchas learned the hard way:
//  - Blank Sets carry junk defaults. Baxcalibur defaults to Intimidate (the calc then applies -1 Atk to the
//    attacker) and Rillaboom to Grassy Surge (turns on Grassy Terrain). Set abilities explicitly, BEFORE boosts.
//  - Selecting Salamence with a Mega item loads Mega Salamence; clearing the item keeps the Mega forme.
//  - The site auto-applies spread reduction in Doubles, so use Singles unless testing spread.
//  - Set nature/SP/item/status/boosts after loading the set; reset the crit checkbox between cases.
(() => {
  const $ = window.$;
  const cases = [
    // a/d: species, m: move, an/dn: nature, asp/dsp: SP [hp,atk,def,spa,spd,spe], item, status, aboost/dboost {atk,def,spa,spd,spe},
    // aab/dab: ability, weather: 'sun'|'rain', format: 'Singles'|'Doubles', crit: true
    {id: 'neutral', a: 'Garchomp', m: 'Earthquake', d: 'Baxcalibur', aab: 'Sand Veil', dab: 'Ice Body', format: 'Singles'},
  ];
  const setVal = (sel, v) => { const e = $(sel); if (e.length) e.val(v).trigger('change'); };
  const out = [];
  for (const c of cases) {
    document.getElementById((c.format || 'Singles').toLowerCase()).click();
    document.getElementById(c.weather || 'clear').click();
    $('#p1 .set-selector').val(c.a + ' (Blank Set)').trigger('change');
    $('#p2 .set-selector').val(c.d + ' (Blank Set)').trigger('change');
    for (const [p, ab, nat, sp, item, status, boost] of [
      ['p1', c.aab, c.an || 'Hardy', c.asp || [0,0,0,0,0,0], c.item || '', c.status || 'Healthy', c.aboost || {}],
      ['p2', c.dab, c.dn || 'Hardy', c.dsp || [0,0,0,0,0,0], '', 'Healthy', c.dboost || {}]]) {
      if (ab !== undefined) setVal(`#${p} .ability`, ab);
      setVal(`#${p} .nature`, nat);
      $(`#${p} .evs`).toArray().slice(0, 6).forEach((e, i) => $(e).val(sp[i]).trigger('input').trigger('change'));
      setVal(`#${p} .item`, item);
      setVal(`#${p} .status`, status);
      ['atk', 'def', 'spa', 'spd', 'spe'].forEach((k, i) => $(`#${p} .boost`).eq(i).val(String(boost[k] || 0)).trigger('change'));
    }
    $('#p1 select.move-selector').each((i, e) => $(e).val(i === 0 ? c.m : '(No Move)').trigger('change'));
    const crit = document.getElementById('critL1');
    if (crit.checked !== !!c.crit) crit.click();
    document.getElementById('resultMoveL1').click();
    out.push({id: c.id, main: $('#mainResult').text(), rolls: $('#damageValues').text(),
      abilities: [$('#p1 .ability').val(), $('#p2 .ability').val()], terrain: $('input[name=terrain]:checked').attr('id')});
    if (crit.checked) crit.click();
  }
  return out;
})();
