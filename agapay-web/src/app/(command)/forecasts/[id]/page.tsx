import {requireStaff} from '@/lib/account-server';
import ForecastRecord from '@/components/ForecastRecord';
export default async function Page({params}:{params:Promise<{id:string}>}){await requireStaff();const {id}=await params;return <ForecastRecord id={id}/>;}
