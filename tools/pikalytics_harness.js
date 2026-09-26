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
    {id: 'toughclaws', a: 'Garchomp', m: 'Dragon Claw', d: 'Baxcalibur', aab: 'Tough Claws', dab: 'Ice Body'},
    {id: 'multiscale', a: 'Garchomp', m: 'Earthquake', d: 'Baxcalibur', aab: 'Sand Veil', dab: 'Multiscale'},
    {id: 'habanberry', a: 'Garchomp', m: 'Dragon Claw', d: 'Baxcalibur', aab: 'Sand Veil', dab: 'Ice Body', ditem: 'Haban Berry'},
    {id: 'reflect_singles', a: 'Garchomp', m: 'Earthquake', d: 'Baxcalibur', aab: 'Sand Veil', dab: 'Ice Body', screen: 'reflect'},
    {id: 'reflect_doubles', a: 'Garchomp', m: 'Dragon Claw', d: 'Baxcalibur', aab: 'Sand Veil', dab: 'Ice Body', screen: 'reflect', format: 'Doubles'},
    {id: 'grassy_halves_eq', a: 'Garchomp', m: 'Earthquake', d: 'Baxcalibur', aab: 'Sand Veil', dab: 'Ice Body', terrain: 'grassy'},
    {id: 'grassy_woodhammer', a: 'Rillaboom', m: 'Wood Hammer', d: 'Garchomp', aab: 'Overgrow', dab: 'Sand Veil', terrain: 'grassy'},
    {id: 'pixilate', a: 'Garchomp', m: 'Body Slam', d: 'Baxcalibur', aab: 'Pixilate', dab: 'Ice Body'},
    {id: 'helpinghand', a: 'Garchomp', m: 'Dragon Claw', d: 'Baxcalibur', aab: 'Sand Veil', dab: 'Ice Body', hh: true},
    {id: 'knockoff', a: 'Incineroar', m: 'Knock Off', d: 'Garchomp', aab: 'Intimidate', dab: 'Sand Veil', ditem: 'Leftovers'},
    {id: 'facade_burn', a: 'Snorlax', m: 'Facade', d: 'Baxcalibur', aab: 'Thick Fat', dab: 'Ice Body', status: 'Burned'},
    {id: 'acrobatics', a: 'Salamence', m: 'Acrobatics', d: 'Garchomp', aab: 'Moxie', dab: 'Sand Veil'},
    {id: 'electroball', a: 'Rotom', m: 'Electro Ball', d: 'Snorlax', aab: 'Levitate', dab: 'Thick Fat'},
    {id: 'gyroball', a: 'Snorlax', m: 'Gyro Ball', d: 'Garchomp', aab: 'Thick Fat', dab: 'Sand Veil'},
    {id: 'foulplay', a: 'Sableye', m: 'Foul Play', d: 'Garchomp', aab: 'Prankster', dab: 'Sand Veil'},
    {id: 'tripleaxel3', a: 'Baxcalibur', m: 'Triple Axel', d: 'Garchomp', aab: 'Ice Body', dab: 'Sand Veil', hits: 3},
    {id: 'bulletseed3', a: 'Rillaboom', m: 'Bullet Seed', d: 'Garchomp', aab: 'Overgrow', dab: 'Sand Veil', hits: 3},
    {id: 'filter', a: 'Garchomp', m: 'Dragon Claw', d: 'Baxcalibur', aab: 'Sand Veil', dab: 'Filter'},
    {id: 'furcoat', a: 'Garchomp', m: 'Earthquake', d: 'Baxcalibur', aab: 'Sand Veil', dab: 'Fur Coat'},
    {id: 'fluffy', a: 'Garchomp', m: 'Dragon Claw', d: 'Baxcalibur', aab: 'Sand Veil', dab: 'Fluffy'},
    {id: 'heatproof', a: 'Incineroar', m: 'Flare Blitz', d: 'Baxcalibur', aab: 'Intimidate', dab: 'Heatproof'},
    {id: 'ironfist', a: 'Scizor', m: 'Bullet Punch', d: 'Baxcalibur', aab: 'Iron Fist', dab: 'Ice Body'},
    {id: 'strongjaw', a: 'Garchomp', m: 'Crunch', d: 'Snorlax', aab: 'Strong Jaw', dab: 'Thick Fat'},
    {id: 'sharpness', a: 'Garchomp', m: 'Aerial Ace', d: 'Snorlax', aab: 'Sharpness', dab: 'Thick Fat'},
    {id: 'megalauncher', a: 'Garchomp', m: 'Dragon Pulse', d: 'Baxcalibur', aab: 'Mega Launcher', dab: 'Ice Body'},
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
      ['p2', c.dab, c.dn || 'Hardy', c.dsp || [0,0,0,0,0,0], c.ditem || '', 'Healthy', c.dboost || {}]]) {
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
    const tog = (id, on) => { const e = document.getElementById(id); if (e.checked !== on) e.click(); };
    document.getElementById(c.terrain || 'noterrain').click();
    tog('reflectR', c.screen === 'reflect'); tog('lightScreenR', c.screen === 'lightScreen'); tog('helpingHandL', !!c.hh);
    if (c.hits) $('#p1 select.move-hits').eq(0).val(String(c.hits)).trigger('change');
    document.getElementById('resultMoveL1').click();
    out.push({id: c.id, main: $('#mainResult').text(), rolls: $('#damageValues').text(),
      abilities: [$('#p1 .ability').val(), $('#p2 .ability').val()], terrain: $('input[name=terrain]:checked').attr('id'), bp: $('#p1 .move-bp').eq(0).val()});
    if (crit.checked) crit.click();
  }
  return out;
})();
