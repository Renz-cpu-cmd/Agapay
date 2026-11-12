import {requireStaff} from '@/lib/account-server';
import ForecastWorkspace from '@/components/ForecastWorkspace';
export default async function Page(){await requireStaff();return <ForecastWorkspace/>;}
