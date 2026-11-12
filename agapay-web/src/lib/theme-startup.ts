export const themeStartupScript = `try{document.documentElement.dataset.theme=localStorage.getItem("agapay-theme")==="dark"?"dark":"light"}catch{document.documentElement.dataset.theme="light"}`;
