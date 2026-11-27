import path from 'node:path';
import {finalizePresentation} from '/Users/ybl/.codex/plugins/cache/openai-primary-runtime/presentations/26.1123.11515/skills/presentations/container_tools/artifact_tool_utils.mjs';
const work=process.cwd(), stage=path.join(work,'.spark-review-build.SKUnrK');
const tools='/Users/ybl/.codex/plugins/cache/openai-primary-runtime/presentations/26.1123.11515/skills/presentations/container_tools';
const result=await finalizePresentation({
 workspaceDir:work,candidatePath:path.join(stage,'candidate.pptx'),
 finalPath:path.join(work,'outputs','Warwick TPC spark study - production review.pptx'),
 pythonExecutable:'/Users/ybl/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3',
 integrityValidatorPath:path.join(tools,'inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(tools,'inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit'],
 explicitTotalSlideCount:12,fontPolicy:{basis:'design',families:['Arial']},
 verifyArtifactToolImport:true,receiptPath:path.join(stage,'validation.json')
});
console.log(result.finalPath);
