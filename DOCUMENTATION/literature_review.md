**Literature**

**Original Thomas Article:**  
[https\://pmc.ncbi.nlm.nih.gov/articles/PMC6536348/pdf/nihms-1526372.pdf](https://pmc.ncbi.nlm.nih.gov/articles/PMC6536348/pdf/nihms-1526372.pdf)  
Core Problem & Clinical Gap:

* Standard T1 or T2 weighted MRI scans lack the intra-thalamic contrast needed to visualize individual thalamic nuclei
* Diffusion tensor imaging methods suffer from low spatial resolution, image distortion, and poor gray matter anisotropy

Proposed Method (sThomas)

* Thomas \= fully automated multi atlas segmentation pipeline for structural MRI
* Relies on WMn MP-RAGE sequence at 7T which maximizes inter nuclear contrast and boundary delineation
* Uses an intermediate template space and automated bilateral cropping to speed up processing to about 10 minutes on a standard desktop PC

Validation and Accuracy

* Evaluated against manual expert segmentations (guided by the Morel Atlas) using DICE coefficients and Volume similarity indices (VSI)
* Achieved high DICE indices (\>= 0.85 for large nuclei like the pulvinar and mediodorsal; \>= 0.70 for smaller nuclei like the habenular and centromedian)
* Outperformed FreeSurfer’s probabilistic atlas module, particularly on small nuclei due to superior intra-thalamic contrast of WMn MP-RAGE

Clinical & Surgical Applications

* Volumetry: Successfully detected significant volume reductions in specific nuclei in multiple sclerosis patients compared to controls
* Neurosurgery: demonstrated effective translation for direct patient specific intra operative targeting of the Ventralis Intermedius nucleus for focused ultrasound thalamotomy and deep brain simulation lead placement

Atlas \= premapped guide used either by a human expert to identify brain structures or by the computer algorithm as an “answer key” to segment a new scan

DICE coefficient: a score from 0 to 1 that measures how well an automated computer segmentation overlaps with a human expert’s hand drawn ground truth  
Calculates the ratio of the overlapping area between the two shapes relative to their total sizes  
→ 0 means zero overlap (complete mismatch)  
→ 1 means 100% exact match  
In medical imaging, standard accuracy can be misleading because most of the scan is empty background  
The DICE coefficient ignores the background and focuses strictly on how accurately the specific shape or structure was captured

DICE coefficient \= measures spatial overlap (whether the computer’s prediction lines up pixel for pixel with the manual drawing)  
VSI \= measures total size (whether the overall volume of the segmented structure matches the expert’s ground truth, regardless of exact alignment)

VSI: compared the total number of pixels in the computer segmentation against the manual ground truth  
→ Scores range from 0 to 1 with 1 meaning that the two volumes are an exact match

DICE \= checks if the pixels line up  
VSI \= checks if the computer estimated the right overall bulk/size for the nucleus  
→ two should be used together to get a complete rigorous picture of the segmentation accuracy

FreeSurfer atlas: widely used open source software suite with a probabilistic atlas module designed to automatically segment subcortical brain structures including thalamic nuclei  
→ used statistical probability models (Bayesian inference) built from ex-vivo MRI and histology data to predict nuclear boundaries  
→ relies on conventional T1 MP-RAGE scans  
→ Comparison with sThomas: Freesurfer relies on standard scans with poor internal thalamic contrast resulting in lower accuracy (particularly for small nuclei) compared to THOMAS and its WMn MP-RAGE approach

**“Toward Reliable Thalamic Segmentation: a rigorous evaluation of automated methods for structural MRI”**  
[https\://www\.medrxiv.org/content/10.1101/2025.09.09.25335439v1.full.pdf+html](https://www.medrxiv.org/content/10.1101/2025.09.09.25335439v1.full.pdf+html)  
Objectives & Comparison: Evaluated three state of the art automated thalamic segmentation methods (FS-T1, diffusion based FS-DTI, and HIPS-THOMAS) across healthy and patient cohorts using two reference atlases (Krauth-Morel and 7TAMI))

HIPS-THOMAS superiority: despite relying on T1-weighted inputs, HIPS-THOMAS consistently outperformed both FreeSurfer methods in accuracy (DICE and AHD metrics) across the vast majority of thalamic nuclei

Limited gains from DTI: FS-DTI showed only marginal improvements over standard FS-T1 for a few specific nuclei, falling well short of HIPS-THOMAS

Clinical Implications & Risk of false negatives: Standard FS-T1 failed to detect meaningful volume differences in key nuclei (AV and pulvinar) when distinguishing between healthy controls and patients with limbic encephalitis whereas HIPS-THOMAS and FS-DTI successfully detected them

Key recommendation: The authors caution against relying on standard FreeSurfer T1 segmentation and recommend adopting HIPS-THOMAS for superior accuracy and resource efficiency

Simplified explanation

Problem: Most researchers map the thalamus using FreeSurfer, even though standard MRI scans are super blurry inside the thalamus. Newer tools exist \- like FreeSurfer’s diffusion powered AI update (FS-DTI) and HIPS-THOMAS but nobody has ever out them head to head against a trusted anatomical reference to see which one actually gets the borders right or which one can reliably spot real brain damage in patients

Solution: Authors tested all three tools (FS-T1, FS-DTI, and HIPS-THOMAS) across two groups of healthy adults and a group of patients with brain inflammation. To score them fairly without spending months hand tracing brains, they judged each tool against two independent reference atlases (one based on microscope histology, one on ultra-high field 7T MRI) and checked how well each tool could tell sick patients apart from healthy people

HIPS-THOMAS won \- beat both FreeSurfer and the new diffusion-based FreeSurfer at matching true anatomy in healthy people even using just a regular T1 scan. Even worse, standard freesurfer struggled to detect real known shrinkage in key memory/visual nuclei in patients whereas HIPS-THOMAS and FS-DTI caught it

**Difference between sTHOMAS and HIPS-THOMAS:**

- sTHOMAS \= original tool that maps out thalamic nuclei using a specialized WMn MRI scan where internal thalamic borders are naturally high contrast
- HIPS-THOMAS \= an upgraded version that takes regular everyday T1 MRI scans and uses a math filter to digitally fake that high contrast WMn look before running the exact same segmentation tool

Main difference: sTHOMAS requires you to acquire a special type of MRI scan from the scanner but HIPS-THOMAS lets you use standard routing hospital MRI scans by synthesizing the needed contrast on the computer first

Freesurfer diffusion update:  
→ a convolutional neural network tool that segments thalamic nuclei by combining standard T1-weighted structural scans with Diffusion tensor imaging data  
→ How it works:

- Problem: standard T1 MRIs show the inside of the thalamus as a blurry gray blob making borders hard to see
- Solution: FS-DTI adds Diffusion MRI which tracks water movement along nerve fibers acting like natural fences between nuclei
- How it works: it feeds both the structural T1 scan (overall shape) and diffusion maps (fiber density and direction) into a trained AI which combines both clues to draw nuclear boundaries

→ it improves upon standard T1-only Freesurfer for a few specific structures; it requires heavy diffusion scan preprocessing and is still outperformed in overall accuracy by HIPS-THOMAS

**Deep Thalamus: A novel deep learning method for automatic segmentation of brain thalamic nuclei from multimodal ultra high resolution MRI**  
[https\://arxiv.org/pdf/2401.07751](https://arxiv.org/pdf/2401.07751)

Limitation of current tools: most existing segmentation packages operate at standard resolution  (1mm isotropic) or rely on monomodal data (such as T1 alone) which struggles with the poor internal tissue contrast of the thalamus

Objective: authors developed DeepThalamus, a multimodal deep learning framework designed to segment thalamic nuclei at ultrahigh resolution (0.5 mm isotropic) to capture finer anatomical detail and prevent volume overestimation

Methods:

- Datasets: 75 ultra high res HCP subjects (T1, T2, WMn) for training/testing, plus 4856 standard clinical T1 scans (ages 3-90) for lifespan robustness
- Preprocessing: Noise filtering, intensity correction, affine registration, and ROI cropping
- Architecture: 3D U-Net convolutional neural network (encoder-decoder with skip connections) optimized for volumetric segmentations
- Strategy: semi supervised multimodal training (T1, T2, WMn) with a built in automated pipeline to process standard 1 mm clinical T1 scans

Results:

- High Accuracy and efficiency: demonstrates state of the art segmentation performance in terms of boundary precision, spatial overlap, and computational speed compared to existing methods
- Multimodal advantage: proves that combining complementary structural contrasts (T1, T2, WMn) yields a richer feature characterization, significantly improving the delineation of small, complex thalamic sub nuclei
- Clinical Scalability: by providing a bridge to standard resolution T1 scans, Deep Thalamus bridges the gap between ultra high field research pipelines and everyday clinical datasets

Simplified explanation:

The Problem:  
Most existing brain mapping tools look at the thalamus using standard low resolution hospital scans (1mm pixels) and only one type of MRI image. Because thalamic nuclei are so tiny and blend together on regular scans, those tools end up guessing or overestimating their size.

DeepThalamus: an AI model trained on ultra high resolution scans (0.5 mm pixels) that combines three different MRI views at once (T1, T2, WMn). Combining three views acts like putting on 3D glasses \- giving the AI way sharper contrast to spot tiny internal borders

Since most hospitals don’t take three ultra high resolution scans for every patient, the authors trained the AI using a semi supervised trick across nearly 5000 normal brain scans. That way the AI learns to apply its high-def knowledge even when you only feed it a single standard hospital MRI

**A Deep Learning Framework for comprehensive segmentation of deep grey nuclei**  
[https\://pmc.ncbi.nlm.nih.gov/articles/PMC12723987/](https://pmc.ncbi.nlm.nih.gov/articles/PMC12723987/)

THOMASINA: fast unified 3D deep learning replacement for sTHOMAS that segments 20 deep gray structures per hemisphere

Issue: Traditional sTHOMAS takes 30-40 minutes per scan and fails when nonlinear registration breaks on enlarged ventricles

How it works:

- For standard T1w inputs, uses HIPS to generate WMn-like contrast first
- Feeds cropped subcortical volumes into a 3D neural network trained on 317 multivendor/multified sTHOMAS labeled scans

Key results:

- SegResNet beat SwinUNETR and DiNTS (Dice \= 0.89 in domain; 0.85 out of domain on unseen ADNI Alzheimer’s data)
- Cuts runtime from 30-40 minutes down to a few seconds
- T1 \+ HIPS synthesis performs nearly identically to native WMn MRI and generalizes across scanner vendors and field strengths

Simplified Summary:

sThomas \= great tool that maps 20 tiny deep brain structures on an MRI  
Works by physically stretching reference brain templates to fit a patient’s scan → takes 30 to 40 minutes per person and sometimes breaks if the patient has an older or diseased brain with unusual shapes

THOMASINA replaces the slow stretching process with a trained AI. Instead of warping templates the AI looks directly at the cropped section of the brain and predicts where all the 20 structures are in a few seconds

Because normal hospital MRIs (T1 scans) make those tiny structures look blurry, THOMASINA first runs a quick math filter (HIPS) that adjusts the image contrast to look like a specialized scan \- allowing the AI to work accurately on standard hospital MRIs from any scanner

Does training THOMASINA on the outputs of sTHOMAS add bias upon bias?  
→ yes if sTHOMAS makes the same mistake every single time, THOMASINA will memorize that exact mistake

→ THOMASINA still ends up being better than sTHOMAS for three reasons:

1. It averages out random glitches
    1. sTHOMAS makes random mistakes on individual scans
    2. THOMASINA studies hundreds of scans at once so it ignores those random one-off glitches and learns the smooth average shape underneath
2. It only studies the A+ examples
    1. Researchers only train THOMASINA on scans where sTHOMAS did a great accurate job, throwing out the messy failures
    2. Hence, the AI learns from sTHOMAS’ best results, not the worse ones
3. It doesn’t crash on weird brains
    1. When sTHOMAS sees a brand new brain with unusual aging or shrinkage, its atlas stretching step can completely break down
    2. Because THOMASINA doesn’t stretch atlases at all \- it just recognizes 3D shapes directly \- it stays steady even on tricky scans

To find the A+ examples: use the Quality control pipeline

1. sTHOMAS warps around 20 different expert atlases: if the atlases vary wildly, the computer flags it as “low confidence” messy segmentation and automatically deletes it from the training pool
2. Size and Volume limits: if the sTHOMAS output has a thalamus with an impossible volume, the delineation is thrown out
3. Left to right symmetry tests: if the left and right thalamus are not about the same, the delineation is thrown out
4. Human experts will inspect a random small slice of the filtered dataset; if the spot checks are good for that small sample, they trust that the automation did the same for the rest of the dataset

**Automatic segmentation of deep gray nuclei using a high resolution 7T magnetic resonance imaging atlas quantification of T1 values in healthy volunteers**  
[https\://hal.science/hal-03516689v1/file/7TAMIbrainEJN\_preprint.pdf](https://hal.science/hal-03516689v1/file/7TAMIbrainEJN_preprint.pdf)

Problem: Normal hospital brain scans are too blurry to clearly see the tiny deep structures inside the brain and standard brain maps only tell you where a structure is but not what it is made of biologically

7TAMIbrain: researchers used an ultrapowerful 7-Tesla research MRI scanner \- which has way higher resolution \- to build a super detailed master brain map (7TAMIbrain) that cleanly maps 24 deep gray matter structures at once

Instead of just drawing borders this tool measures the exact physical magnetic fingerprint (T1 relaxation value) of the tissue inside every single structure. That way doctors and researchers can spot subtle chemical or structural changes in diseases like Parkinson's or multiple sclerosis not just physical shrinkage

**Deep Label Fusion: A generalizable hybrid multi-atlas and deep convolutional neural network for medical image segmentation**  
[https\://pmc.ncbi.nlm.nih.gov/articles/PMC10009820/pdf/nihms-1849827.pdf](https://pmc.ncbi.nlm.nih.gov/articles/PMC10009820/pdf/nihms-1849827.pdf)

Problem: Old school multi atlas software uses a math formula to figure out which expert brain map to trust when voting on a patient’s scan. But that math formula is rigid, slow, and often gets tripped up when a patient’s brain anatomy is a little unusual or messy

Solution (Deep Label Fusion): instead of relying on rigid old math formulas to count votes, the researchers trained a smart AI (a U-Net) to do the voting. It still uses expert brain maps as its reliable reference guides but the AI handles the final decision of how much weight to give each atlas

Secret Sauce: fully AI based models sometimes hallucinate or draw wild shapes when they see a scan that looks different from their training data. This tool avoids that because it keeps the safety guardrails of real atlas maps using deep learning strictly to make the voting smarter and faster.

**Model Run Down**

Pipeline of the THOMAS family algorithms developed by Manojkumar Saranthan’s group:

1. THOMAS \~ 2019
    1. Problem: on regular hospital MRIs, internal thalamic nuclei completely blend together into a blurry gray blob
    2. Solution: researchers invented a specialized WMn scan that darkens surrounding tissue so internal thalamic boundaries pop, paired with an automated multiatlas tool to map 12 nuclei in about 10 minutes
    3. Catch: it only works on specialized WMn scans \- you can’t use it on normal everyday hospital T1 scans
2. HIPS-THOMAS \~ 2024
    1. Problem: Most large brain databases and hospital records only contain standard T1 weighted scans locking researchers out of using THOMAS
    2. Solution: They added a math filter called HIPS that acts like a digital translator \- artificially rewriting standard T1 scan contrast to look like WMn scans right before running THOMAS
3. sTHOMAS \~ 2025
    1. Problem: The thalamus doesn’t work in isolation \- the researchers also needed to map neighboring deep structures all at once
    2. Solution: They expanded the multiatlas library and pipeline into subcortical THOMAS (sTHOMAS) scaling up coverage to 20 deep gray structures per hemisphere
    3. Catch: Because it was mapping way more structures and stretching larger brain regions, processing time spiked to 30-40 minutes per brain
4. THOMASINA \~ late 2025
    1. Problem: Waiting 30-40 minutes per scan makes multiatlas stretching impossible when you are analyzing massive population datasets with tens of thousands of brains
    2. Solution: They replaced the slow template stretching entirely with a trained AI using sTHOMAS’s output. It keeps the HIPS contrast converter for standard T1 scans but spits out all 20 deep brain structures in under 10 seconds
    3. THOMASINA is not really about improving the theoretical accuracy threshold of sTHOMAS but more about making it fast, crash proof, and deployable at a larger scale i.e. THOMASINA makes sTHOMAS more practical to use

DeepThalamus \~ 2024

1. Problem: standard hospital MRIs make internal thalamic nuclei look like a gray blur and single scan AI models lack the sharp contrast needed to trace tiny adjacent borders accurately
2. Solution: a 3D U-Net trained on ultra-high resolution (0.5 mm) scans that fuses three MRI views at once (T1, T2, WMn)


→ splits the MRI image into 2D slices so that the algorithm can process each of them at high resolutions without running out of memory or shrinking it  
→ this eliminates through plane blurriness: the smearing or loss of fine detail you get when looking at a 3D medical scan from the side caused by the slices being chopped too thick

3. Secret Sauce: a semi-supervised training design across thousands of scans that teaches the AI its “high-def” knowledge allowing it to accurately segment standard everyday hospital MRIs even when multi-modal ultra high field scans aren’t available’  
   → trains first on high resolution images to learn the anatomical rules of where every nucleus sits and what a crisp boundary looks like  
   → then trains on thousands of standard scans to learn real world messiness such as different scanners, varying patient ages, minor motion artifacts, and standard hospital blurriness

Deep Label Fusion \~ 2023

1. Problem: Traditional multiatlas voting relies on rigid, slow mathematical formulas that compare local pixel brightness to guess which reference atlas to trust, easily breaking down when scanner noise or unusual contrast tricks the math
2. Solution: A 3D convolutional neural network that replaces the old math formulas to handle the final voxel by voxel voting process learning complex anatomical context instead of just checking raw brightness matching
3. Secret Sauce: a hybrid architecture that keeps the safety guardrails of expert reference atlases to prevent AI hallucinations using deep learning strictly to generate smarter more context aware spatial weighting maps for the final label fusion

Note: sTHOMAS uses the “old mathematical formulas” (patch based JLF calculations) that were modified in Deep Label fusion