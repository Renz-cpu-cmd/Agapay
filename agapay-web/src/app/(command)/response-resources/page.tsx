import {requireStaff} from "@/lib/account-server";
import ResponseResources from "@/components/ResponseResources";

export default async function ResourcePage(){
  await requireStaff();
  return <ResponseResources/>;
}
