// Logic check for the portable local view. This does not render a browser page.
import fs from "node:fs";
import vm from "node:vm";

const pageFiles = {before:"Alex_B_Plus_Investigation_View.html",two_timeouts:"Alex_B_Plus_Timeouts.html",two_valid_404s:"Alex_B_Plus_404s.html",post_404_timeout:"Alex_B_Plus_404s_Then_Timeout.html"};
for (const [scenario,filename] of Object.entries(pageFiles)) {
  const page=fs.readFileSync(new URL("./"+filename,import.meta.url),"utf8");
  if (!page.includes(`const INITIAL_SCENARIO = "${scenario}";`)) throw new Error(`Wrong starting state: ${filename}`);
}
const html = fs.readFileSync(new URL("./Alex_B_Plus_Investigation_View.html", import.meta.url), "utf8");
const indexHtml = fs.readFileSync(new URL("./index.html", import.meta.url), "utf8");
if (indexHtml !== html) throw new Error("The recruiter landing page differs from the before-checks view");
for (const filename of Object.values(pageFiles)) {
  if (!html.includes(`href="${filename}"`)) throw new Error(`Missing native branch link: ${filename}`);
}
const start = html.lastIndexOf("<script>");
const end = html.lastIndexOf("</script>");
if (start < 0 || end <= start || html.includes("/*__SYNTHETIC_DATA__*/") || html.includes("/*__INITIAL_SCENARIO__*/")) {
  throw new Error("Generated page is missing its embedded synthetic data");
}
if (/<script\s+src=|<iframe|fetch\s*\(|href\s*=\s*["']https?:/i.test(html)) {
  throw new Error("The local page unexpectedly refers to network content");
}
const script = html.slice(start + "<script>".length, end);
new vm.Script(script);

const ids = ["runtimeStatus","formMessage","scenarioLabel","caseUrl","reportCount","systemBand","systemTime","analystBand","analystStatus","effectiveBand","reviewFlag","reasonCodes","reasonExplanation","policyVersion","evidenceProfile","timeline","missingChecks","scopeNote","recommendationHistory","decisionHistory","decisionPreview","chosenBand","rationale","decisionForm","exportBtn","resetBtn"];
const elements = Object.fromEntries(ids.map(id => [id, {textContent:"",innerHTML:"",value:"",className:"",hidden:false,handlers:{},addEventListener(type,fn){this.handlers[type]=fn;}}]));
const steps = Object.keys(pageFiles).map(key => ({dataset:{scenario:key},attributes:{},handlers:{},setAttribute(name,value){this.attributes[name]=value;},addEventListener(type,fn){this.handlers[type]=fn;}}));
let exportedBlob = null, exportClicked = false;
class MockBlob {constructor(parts,options){this.parts=parts;this.type=options.type;}}
const MockURL = {createObjectURL(blob){exportedBlob=blob;return "blob:synthetic-audit";},revokeObjectURL(){}};
const document = {getElementById(id){if(!elements[id])throw Error(`Missing mock element ${id}`);return elements[id];},querySelectorAll(selector){if(selector!==".step")throw Error(`Unexpected selector ${selector}`);return steps;},createElement(tag){if(tag!=="a")throw Error("Unexpected element");return {click(){exportClicked=true;},remove(){}};},body:{append(){}}};
const context=vm.createContext({document,Intl,Date,Object,String,console,Blob:MockBlob,URL:MockURL,setTimeout:fn=>fn()});
vm.runInContext(script, context, {timeout:2000});
const assert = (condition,message) => {if(!condition)throw new Error(message);};

assert(elements.scenarioLabel.textContent === "Before follow-up checks", "Initial scenario is not before checks");
assert(elements.runtimeStatus.textContent.startsWith("Interactive controls ready"), "The page did not mark its script as running");
assert(elements.systemBand.textContent === "Review now" && elements.effectiveBand.textContent === "Review now", "Initial band is wrong");
assert(elements.evidenceProfile.innerHTML.includes("Not checked"), "Initial missing evidence is hidden");
assert(elements.decisionPreview.textContent.includes("O-B-DISTRIBUTION-PLUS"), "Decision preview lost the evidence reference");
assert((elements.timeline.innerHTML.match(/class="event /g)||[]).length === 3, "Initial timeline must have two reports and distribution");
console.log("PASS initial: Review now, two reports, distribution, unchecked page");

vm.runInContext('setScenario("two_timeouts")',context);
assert(elements.evidenceProfile.innerHTML.includes("Check failed"), "Timeouts were not shown as failed checks");
assert(elements.effectiveBand.textContent === "Review now", "Timeout branch was downgraded");
assert((elements.timeline.innerHTML.match(/class="event /g)||[]).length === 5, "Timeout timeline lost events");
console.log("PASS timeouts: failed checks, Review now, full timeline");

vm.runInContext('setScenario("two_valid_404s")',context);
assert(elements.systemBand.textContent === "Review now", "404 branch changed the engine recommendation");
assert(elements.effectiveBand.textContent === "Review today", "404 fixture analyst decision is missing");
assert(elements.evidenceProfile.innerHTML.includes("Checked · not found"), "404s are not shown as scoped negatives");
assert(elements.decisionHistory.innerHTML.includes("fictional-analyst-01"), "Fixture decision is missing from history");
console.log("PASS 404: system now, fictional analyst today, scoped checks shown");

vm.runInContext('setScenario("post_404_timeout")',context);
assert(elements.systemBand.textContent === "Review now" && elements.effectiveBand.textContent === "Review today", "Later timeout silently changed a band");
assert(elements.reviewFlag.hidden === false && elements.reviewFlag.textContent.includes("O-B-POST-404-TIMEOUT-V3"), "Reassessment flag is missing");
assert(elements.evidenceProfile.innerHTML.includes("Check failed"), "Latest failed check is missing from profile");
assert(elements.timeline.innerHTML.includes("exact path") && (elements.timeline.innerHTML.match(/class="event /g)||[]).length===6, "Later branch lost observation history");
assert((elements.recommendationHistory.innerHTML.match(/class="history-item"/g)||[]).length===3, "Later branch lost recommendation history");
elements.exportBtn.handlers.click();
const reviewExport=JSON.parse(exportedBlob?.parts[0] || "null");
assert(reviewExport.decision_review?.status==="reassessment_needed" && reviewExport.observation_history.length===4, "Audit export lost reassessment evidence");
console.log("PASS later timeout: old decision retained, flagged for human reassessment");

vm.runInContext('setScenario("two_valid_404s")',context);

elements.chosenBand.value = "review_now";
elements.chosenBand.handlers.change();
assert(elements.decisionPreview.textContent.includes("your choice: Review now"), "Decision preview did not update");
elements.rationale.value = "I retain immediate review because the distribution signal warrants another authorized check.";
elements.decisionForm.handlers.submit({preventDefault(){}});
assert(elements.effectiveBand.textContent === "Review now", "A session override did not change the effective band");
assert(elements.decisionHistory.innerHTML.includes("portfolio-demo-analyst"), "New decision was not appended");
assert(elements.decisionHistory.innerHTML.includes("fictional-analyst-01"), "New decision overwrote the fixture decision");
elements.exportBtn.handlers.click();
const exported = JSON.parse(exportedBlob?.parts[0] || "null");
assert(exportClicked && exported.session_decisions.length===1, "Audit export omitted the session decision");
assert(exported.fixture_decisions.length===1 && exported.observation_history.length===3, "Audit export lost fixture history");
vm.runInContext('setScenario("two_timeouts")',context);vm.runInContext('setScenario("two_valid_404s")',context);
assert(elements.effectiveBand.textContent === "Review now", "Session decision did not survive in-memory scenario changes");
elements.resetBtn.handlers.click();
assert(elements.effectiveBand.textContent === "Review today", "Reset did not restore the fixture decision");
console.log("PASS override: appended separately, exportable, resets without changing fixture");

for (const [scenario,filename] of Object.entries(pageFiles)) {
  if (scenario==="before") continue;
  const page=fs.readFileSync(new URL("./"+filename,import.meta.url),"utf8");
  const branchScript=page.slice(page.lastIndexOf("<script>")+8,page.lastIndexOf("</script>"));
  vm.runInNewContext(branchScript,{document,Intl,Date,Object,String,console,Blob:MockBlob,URL:MockURL,setTimeout:fn=>fn()},{timeout:2000});
  const expectedLabel=scenario==="two_timeouts"?"Two timeouts":scenario==="post_404_timeout"?"Later timeout after two 404s":"Two valid 404s";
  const expectedEffective=scenario==="two_timeouts"?"Review now":"Review today";
  assert(elements.scenarioLabel.textContent===expectedLabel && elements.effectiveBand.textContent===expectedEffective,`Direct page did not open in ${scenario}`);
}
console.log("PASS direct pages: each standalone file opens in its intended branch");
