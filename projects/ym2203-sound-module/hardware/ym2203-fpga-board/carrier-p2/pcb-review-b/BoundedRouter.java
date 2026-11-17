// SPDX-License-Identifier: MIT
// Local process wrapper for Freerouting2.1.0, no hardware or network access required.
import app.freerouting.Freerouting;
import app.freerouting.management.RoutingJobScheduler;
import app.freerouting.core.RoutingJob;
import app.freerouting.interactive.HeadlessBoardManager;
import java.io.*;
import java.util.*;
public class BoundedRouter {
 public static void main(String[] args) throws Exception {
  int passes=Integer.parseInt(System.getProperty("p2.router.passes","25"));
  String out=args[0]; int seconds=Integer.parseInt(args[1]); String[] cli=Arrays.copyOfRange(args,2,args.length);
  Thread monitor=new Thread(()->{try{
   long until=System.currentTimeMillis()+seconds*1000L; RoutingJob job=null;
   while(System.currentTimeMillis()<until){
    Thread.sleep(250);
    RoutingJob[] jobs=RoutingJobScheduler.getInstance().listJobs();
    if(jobs.length>0){job=jobs[jobs.length-1]; if(job.routerSettings!=null){job.routerSettings.maxPasses=passes;job.routerSettings.set_stop_pass_no(passes);job.routerSettings.setRunOptimizer(false);}}
   }
   if(job==null || job.board==null)throw new Exception("No routed board");
   if(job.thread!=null){job.thread.requestStop();job.thread.join(30000); if(job.thread.isAlive())throw new Exception("Router did not stop safely");}
   HeadlessBoardManager manager=new HeadlessBoardManager(Locale.US,job);manager.replaceRoutingBoard(job.board);
   try(OutputStream stream=new FileOutputStream(out)){if(!manager.saveAsSpecctraSessionSes(stream,"p2-b"))throw new Exception("SES export failed");}
   System.out.println("BOUNDED SES SAVED "+out);System.exit(0);
  }catch(Throwable e){e.printStackTrace();System.exit(2);}},"bounded-export");
  monitor.setDaemon(true);monitor.start();Freerouting.main(cli);
 }
}
