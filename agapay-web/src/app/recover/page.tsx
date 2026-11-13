import AccountRecovery from "@/components/AccountRecovery";
import type {Metadata} from "next";
export const metadata:Metadata={title:"AGAPAY account recovery",referrer:"no-referrer",robots:{index:false,follow:false}};
export default function RecoveryPage(){return <AccountRecovery/>;}
