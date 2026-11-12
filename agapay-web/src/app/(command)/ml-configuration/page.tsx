import {requireStaff} from "@/lib/account-server";
import MLConfiguration from "@/components/MLConfiguration";

export default async function Page(){await requireStaff();return <MLConfiguration/>;}
