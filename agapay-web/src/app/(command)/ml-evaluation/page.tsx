import {requireStaff} from "@/lib/account-server";
import MLEvaluation from "@/components/MLEvaluation";
export default async function Page(){await requireStaff();return <MLEvaluation/>;}
