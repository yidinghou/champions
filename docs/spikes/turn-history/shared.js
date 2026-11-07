// Mock battle: Incineroar (p1) vs Garchomp (p2). Static data, not wired to the engine.
const NODES = {
  s0: {id:"s0", turn:0, parent:null, label:"Start", summary:"Incineroar 170/170 · Garchomp 183/183", hp:[100,100], lines:[["Battle starts"]]},
  t1: {id:"t1", turn:1, parent:"s0", label:"Fake Out", summary:"Garchomp flinched", hp:[100,94],
       lines:[["p1","Incineroar"," used Fake Out"],["p2","Garchomp"," flinched"],["end","End of turn"]]},
  t2: {id:"t2", turn:2, parent:"t1", label:"Tailwind / miss", summary:"Tailwind up · Aqua Tail missed", hp:[100,94], field:["Tailwind p1 · 4"],
       lines:[["p1","Incineroar"," used Tailwind"],["p2","Garchomp","'s Aqua Tail missed ","p1","Incineroar"],["end","End of turn"]]},
  t3: {id:"t3", turn:3, parent:"t2", label:"Mud Slap", summary:"Incineroar moves first (Tailwind)", hp:[71,82], field:["Tailwind p1 · 3"],
       lines:[["p1","Incineroar"," used Mud Slap"],["p2","Garchomp"," lost 12%"],["p2","Garchomp"," used Aqua Tail"],["p1","Incineroar"," lost 29%"],["end","End of turn"]]},
  t4: {id:"t4", turn:4, parent:"t3", label:"KO", summary:"Garchomp faints · p1 wins", hp:[71,0], field:["Tailwind p1 · 2"], win:true,
       lines:[["p1","Incineroar"," used Mud Slap"],["p2","Garchomp"," fainted"],["end","Player 1 wins"]]},
  b3: {id:"b3", turn:3, parent:"t2", label:"Fake Out (fails)", summary:"Fake Out failed · took Aqua Tail", hp:[66,94], field:["Tailwind p1 · 3"], alt:true,
       lines:[["p1","Incineroar"," used Fake Out — failed"],["p2","Garchomp"," used Aqua Tail"],["p1","Incineroar"," lost 34%"],["end","End of turn"]]},
};
const MAIN = ["s0","t1","t2","t3","t4"];
const lineHtml = (l) => { if (l[0]==="end") return `<b class="${l[1].includes("Player 1")?"p1":""}">${l[1]}</b>`;
  let out=""; for (let i=0;i<l.length;){ if (l[i]==="p1"||l[i]==="p2"){ out+=`<span class="${l[i]}">${l[i+1]}</span>`; i+=2; } else { out+=l[i]; i+=1; } } return out; };
