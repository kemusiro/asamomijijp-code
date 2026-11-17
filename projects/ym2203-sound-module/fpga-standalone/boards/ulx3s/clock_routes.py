# SPDX-License-Identifier: MIT
# nextpnr --post-route hook: expose actual clock placement/routes and model limits.
import json,os
rows=[]
for name,cell in ctx.cells:
 if str(cell.type) in ['DCCA','EHXPLLL']:
  ports=[]
  for port,info in cell.ports:
   if port not in ['CLKI','CLKFB','CLKOP','CLKINTFB','CLKO'] or not info.net:continue
   net=info.net
   ends=[{'cell':str(u.cell.name),'port':str(u.port),'model_route_ns':ctx.getDelayNS(ctx.getNetinfoRouteDelay(net,u))} for u in net.users]
   ds=[u['model_route_ns'] for u in ends]
   ports.append({'port':str(port),'net':str(net.name),'sink_count':len(ends),'model_min_ns':min(ds) if ds else None,'model_max_ns':max(ds) if ds else None,'sinks':ends if len(ends)<8 else []})
  rows.append({'cell':str(name),'type':str(cell.type),'bel':str(cell.bel),'ports':ports})
with open(os.environ['F1_CLOCK_ROUTES'],'w') as f:json.dump({'clock_cells':rows,'limit':'ECP5 nextpnr global distribution delay is zero in this model. Routed clock resources are checked; silicon clock skew/insertion, jitter and analog PLL lock are not signed off.'},f,indent=2);f.write('\n')
