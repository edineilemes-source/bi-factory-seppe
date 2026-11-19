/* Apache ECharts configuration helpers for BI Factory SEPPE.
 * Shared by ECharts Studio and the Product Visual Editor.
 * RREO is accumulated: sorting and displaying does not sum bimesters.
 * Apache-2.0-compatible local application code; requires ECharts 5 (Apache-2.0).
 */
(function(global){
  "use strict";
  const money=v=>new Intl.NumberFormat("pt-BR",{style:"currency",currency:"BRL",maximumFractionDigits:2}).format(v);
  const compact=v=>{
    const n=Number(v);
    if(!Number.isFinite(n))return String(v);
    const a=Math.abs(n);
    if(a>=1e9)return (n/1e9).toLocaleString("pt-BR",{maximumFractionDigits:1})+" bi";
    if(a>=1e6)return (n/1e6).toLocaleString("pt-BR",{maximumFractionDigits:1})+" mi";
    if(a>=1e3)return (n/1e3).toLocaleString("pt-BR",{maximumFractionDigits:1})+" mil";
    return n.toLocaleString("pt-BR",{maximumFractionDigits:2});
  };
  function number(v){
    if(v===null||v===undefined||v==="")return null;
    const n=Number(v);
    return Number.isFinite(n)?n:null;
  }
  function build({spec,rows,keys,metrics,labels}){
    const type=spec.type||"BAR";
    const selectedColors=(spec.colors||[]).filter(Boolean);
    const color=selectedColors.length?selectedColors:["#259ea6","#c7e88a","#ef993e","#6f7ed3","#ec6b82"];
    const showLabels=Boolean(spec.showLabels||type==="RANKING");
    const pie=type==="PIE"||type==="DONUT";
    const axisLabel={formatter:compact,hideOverlap:true};
    const base={color,animationDuration:350,
      legend:{type:"scroll",top:0,left:"center",textStyle:{color:"#56616a"}},
      tooltip:{trigger:pie?"item":"axis",confine:true},
      grid:{left:18,right:26,top:52,bottom:45,containLabel:true},
      textStyle:{color:spec.text||"#203047",fontFamily:"Arial"}
    };
    if(pie){
      const key=keys[0];
      base.tooltip={trigger:"item",confine:true,valueFormatter:v=>money(v)};
      base.legend={type:"scroll",bottom:0,top:"auto"};
      base.series=[{type:"pie",radius:type==="DONUT"?["46%","71%"]:"70%",center:["50%","46%"],
        label:{show:showLabels,formatter:"{b}"},
        data:rows.map((row,i)=>({name:labels[i],value:number(row[key])})).filter(x=>x.value!==null)}];
      return base;
    }
    if(type==="SCATTER"){
      const xMetric=spec.scatterX&&keys.includes(spec.scatterX)?spec.scatterX:keys[0];
      const yMetric=spec.scatterY&&keys.includes(spec.scatterY)?spec.scatterY:keys.find(k=>k!==xMetric);
      if(!xMetric||!yMetric)return null;
      base.legend={show:false};
      base.tooltip={trigger:"item",confine:true,formatter:p=>{
        const v=p.data||[];
        return String(v[2]||"")+"<div>"+String(metrics[keys.indexOf(xMetric)]||"X")+": "+money(v[0])+"</div>"+
          "<div>"+String(metrics[keys.indexOf(yMetric)]||"Y")+": "+money(v[1])+"</div>";
      }};
      base.xAxis={type:"value",name:metrics[keys.indexOf(xMetric)]||"X",nameLocation:"middle",nameGap:30,scale:true,axisLabel};
      base.yAxis={type:"value",name:metrics[keys.indexOf(yMetric)]||"Y",nameLocation:"middle",nameGap:55,scale:true,axisLabel};
      base.grid={left:24,right:40,top:35,bottom:60,containLabel:true};
      base.series=[{name:"Dispersão",type:"scatter",symbolSize:12,
        itemStyle:{color:color[0],opacity:0.85},
        label:{show:showLabels,formatter:p=>p.data[2],position:"top"},
        data:rows.map((row,i)=>[number(row[xMetric]),number(row[yMetric]),labels[i]])
          .filter(pair=>pair[0]!==null&&pair[1]!==null)}];
      return base;
    }
    if(type==="RANKING"){
      const key=keys[0];
      if(!key)return null;
      let ranking=rows.map((row,i)=>({name:labels[i],value:number(row[key])}))
        .filter(x=>x.value!==null).sort((a,b)=>b.value-a.value);
      const topN=Number(spec.topN);
      if(Number.isInteger(topN)&&topN>0)ranking=ranking.slice(0,topN);
      base.tooltip={trigger:"axis",axisPointer:{type:"shadow"},valueFormatter:money};
      base.legend={show:false};
      base.grid={left:12,right:76,top:12,bottom:30,containLabel:true};
      base.xAxis={type:"value",axisLabel};
      base.yAxis={type:"category",inverse:true,data:ranking.map(x=>x.name),
        axisLabel:{width:170,overflow:"truncate",interval:0,fontSize:11}};
      base.series=[{name:metrics[0]||"Valor",type:"bar",barMaxWidth:24,
        label:{show:showLabels,position:"right",fontSize:10,
          formatter:p=>compact(p.value)},data:ranking.map(x=>x.value)}];
      return base;
    }
    const horizontal=type==="HORIZONTAL";
    const category={type:"category",data:labels,axisLabel:{
      hideOverlap:true,interval:"auto",width:120,overflow:"truncate"}};
    const value={type:"value",axisLabel};
    base.xAxis=horizontal?value:category;
    base.yAxis=horizontal?category:value;
    base.tooltip={trigger:"axis",axisPointer:{type:"shadow"},valueFormatter:money};
    base.series=keys.map((key,index)=>({
      name:metrics[index]||key,
      type:type==="LINE"||type==="AREA"?"line":type==="POINTS"?"scatter":"bar",
      smooth:false,
      areaStyle:type==="AREA"?{}:undefined,
      stack:type==="STACK"?"total":undefined,
      symbolSize:type==="POINTS"?11:undefined,
      barMaxWidth:44,
      label:{show:showLabels,position:type==="LINE"||type==="AREA"||type==="POINTS"?"top":horizontal?"right":"top",
        fontSize:10,formatter:p=>p.value==null?"":compact(p.value)},
      data:rows.map(row=>number(row[key]))
    }));
    return base;
  }
  global.BIFactoryChartOptions={build,number,money,compact};
})(window);
