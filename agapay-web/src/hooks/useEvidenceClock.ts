"use client";
import {useEffect,useState} from "react";
export function useEvidenceClock(){
  const [now,setNow]=useState(0);
  useEffect(()=>{
    const tick=()=>setNow(document.hidden?0:Date.now());
    tick();const timer=setInterval(tick,1000);
    document.addEventListener("visibilitychange",tick);
    return()=>{clearInterval(timer);document.removeEventListener("visibilitychange",tick);};
  },[]);
  return now;
}
