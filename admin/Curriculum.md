## Philosophy of the Project Progression

- The sequence of four projects are designed to prepare the students to complete their own independent research project at the end of the program.
- There are five projects, building in complexity and autonomy.  The topics are:
     1. Introduce your home watershed - a qualitative presentation of the student's level of hydrogeologic knowledge upon entering the program - water availability and quality
     2. Explain an Arizona Department of Water Resources model report to a general audience - tackling technical concepts and presentation of data without the need to complete quantitative analyses - water balance and salinity
     3. Use the MODFLOW model from the previous study to examine zone of influence, capture zone, and capture and to explore superposition - modifying and using a MODFLOW model to understand hydrogeologic systems - pumping effects and arsenic
     4. Use analytical models to examine higher dimensional problems, specifically 'fair' water allocation in the Little Plover - using groundwater models to address water resources decision making - capture
- Each project lasts five weeks and students are given weekly milestones (ungraded) to guide them in planning completion of a long term project
- Projects 3 and 4 are completd in three-person teams.  Each team has a project manager, an analyst, and a data wrangler with specified roles.
- After Project 4, students begin working on their indepedent research.  They will propose their scientific question, develop milestones, complete and defend their work.  Students will continue a minimum of 6 weeks in the summer with no classes, working exclusively on their projects. 

## -----------------------------------------------------------------------------------
## The Little Plover Study - General Learning Objectives
 
At this point, the students have read, summarized, and presented on a technical report.  They have also used MODFLOW and chemical analyses to better understand some technical aspects of a hydrogeologic system.  For this project, we want to put the emphasis on how hydrogeology can be used to support improved water resources decision making.  Technical elements will be included, but the focus will be better understanding the value and limitations of hydrogeologic analysis in a human context.  To help them to take this perspective, the project should start with presenting the question of how water can be shared fairly.  Then we will introduce the tools that can be used to quantify their fair-sharing schemes.  In the end, we want them to spend time reflecting on the hydrogeologist's role in informing debate without, necessarily, taking a position or making the decisions. 
 
## -----------------------------------------------------------------------------------
## The Little Plover Study - Milestones
0. OVERALL OBJECTIVE
- Your task is to describe how a groundwater model can be used to support and improve water allocation decision making in a multi-stakeholder context as part of a team of experts.
- Your weekly objectives and subtasks are listed below.
- Be sure to read all of the milestones at the beginning of the project so that you know how they fit together and support the final report and presentation.

1. BACKGROUND
- Read about the area to understand the hydrogeologic and hydrometeorological setting.
- Learn about how and why the Little Plover was deemed to be oversubscribed.
- Humanize a range of water users to understand their relationship with groundwater and how they value it.  That is, while hydrologic models report in units of water, stakeholders make decisions based on economic value, or environmental health, or water supply reliability.  How can hydrologic model results be translated to these units?  Which datasets would you need?  Are they publicly available?  At this stage, you should propose how this could be done, constructing a workflow diagram, but you do not need to find the site-specific data to accomplish this translation.
- Because water resources management requires actions from multiple participants, there are commonly multiple possible plans to meet any objective.  In the LPR, you can assume that the pumping rate can be controlled separately for each well.  Based on fairness, equity, or other value measures, describe at least three approaches that could be used to reapportion water use in the LPR.  Each approach should allow for variable total reduction in water extraction.  For example, each user could be reduced by a fixed percent based on their average pumping over the last ten years: the fixed percent could be 1, 2, 5, 25 until the total capture is acceptable.  Justify the fairness of each of your three approaches.
- Background references will be provided.

2. THE NUMERICAL SOLUTION
- 'Read' the MODFLOW model and 'reverse engineer' a conceptual model of the Little Plover that is consistent with the model.  This should include a description of the components of the water balance, boundary conditions, hydraulic parameter distributions, and pumping scheduling.
- Run the stready state MODFLOW model once to determine the run time.  Include a short description of what is and is not described with a steady state model that is relevant to stream capture.  
- Discuss how the MODFLOW model could be used to determine the depletion reduction (or fraction of water provided by capturing streamflow) for a given well.
- Discuss how the MODFLOW model coudl be used to determine the recution in stream capture that would result by altering the steady state pumping rate by a different amount for ten different wells.  Estimate the time that would be required to modify the MODFLOW input files, run the model, and extract the results to be used to determine the impact of this single pumping reduction plan on stream capture.
- The MODFLOW file, including all input files, will be provided.

3. THE ANALYTICAL SOLUTION
- Read supporting publications that underlie the analytical solution.
- Learn how to run the analytical code.
- Compare the capture calculated for one well with the analytical solution with that based on MODFLOW.  Discuss why it is or is not acceptable to validate an analytical solution based on the similarity of its results to a numerical model; compare this to calibrating a groundwater model against observations.
- Use the analytical model to determine the capture fraction of each well in the basin.
- Inspect the analytical solution to determine which parameters are most important. How are these represented in the MODFLOW formulation? Is anything included in the MODFLOW formulation missing from the analytical. 
- Use the analytical model to implement one reallocation strategy to hit a single target reduction in total capture [starting with a historical value of 8.6 CFS at Hoover, evaluate configurations of pumping that do not reduce from this value to below to Public Rights Flow of 6.8 CFS at Hoover].  For this example of simple optimization, demonstrate that there are mulitple combinations of reducing pumping in wells to achieve the goal and then come up with a basis on which to choose the 'best' strategy (e.g. minimum overall reduction of pumping).  Relate this strategy to the fairness, equity, or other measures that you identified previously.
- Reflect on the value of using the analytical model instead of MODFLOW for this analysis - provide an estimate of the time saved.
- References describing the analytical solution, the code to run the analytical solution to determine depletion reduction for one well, and the code to determine the change in stream capture by altering pumping from multiple wells are provided.

4. PARETO OPTIMIZATION  
- Repeat the previous step for multiple target reductions of capture.  The purpose-built code will show the Pareto front and dominated (suboptimal) solutions.  Explain what is meant by Pareto Optimal solutions in a way that it relates dominated solutions to the Pareto Front and it explains the need for additional constraints to find a single 'best' solution.
- Choose one of your 'fairness' criteria and find the Pareto solutions with this added.
- Plot the Pareto optimal solutions with and without the fairness criterion on the same axes.  Discuss the 'costs' and 'benefits' of adding a fairness criterion.  
- Code to implement Pareto optimization for stream capture versus pumping reduction with the option to add a 'fairness' criterion is provided.

5. PARETO OPTIMIZATION IN DECISION-RELEVANT UNITS  
- Convert stream flow to probability of fish occurrence units and well pumping to agricultural receipts.
- Complete three Pareto optimizations: pumping reduction and fish occurence; streamflow and agricultural receipts; and agricultural receipts and fish occurence. Discuss how each curve could be used to support water water allocation decision-making.
- Plot the three Pareto fronts on the streamflow versus pumping reduction axes.  Discuss the 'costs' and 'benefits' of optimizing in decision-relevant units.
- Repeat the agricultural receipts and fish occurence optimization with three different fairness criteria applied.  Discuss how these solutions could be used to guide water resources allocation decisions.
- Reflect on which parts of this process you feel should and should not be in the professional domain of a hydrogeologist.  For any area that is outside of the scope of a hydrogeologist, justify its exclusion and, if possible, describe the expertise needed to address this area.
- Curves relating probability of fish occurence versus streamflow and an explanation of how well pumping is converted to agricultural receipts are provided.  A code that can implement one or both of these conversions and complete Pareto optimization with or without a fairness criterion applied is provided.

6. REPORT AND PRESENTATION
- Your audience will be technical staff at the Department of Natural Resources as well as stakeholders who might be affected directly by pumping reductions.
- You should present your technical work in sufficient detail that a professional hydrogeologist could replicate your work. For context, you have been called in as a technical expert to advise a process by which elected officials, government experts, and citizens will jointly decide how to reallocate pumping rates.  
- You should clearly state any assumptions that you make about how different stakeholders value water.
- The tone of your report should be aimed at a professional audience, include explanations of key concepts in the appendices for non-experts.
- Your presentation should be no more than 15 minutes long plus 10 minutes for questions.
- Expect to get questions that are based on your technical approach as well as questions from stakeholders who may not be pleased with your recommendations.  Be prepared to describe and explain your fairness criteria.
 
## -----------------------------------------------------------------------------------
## The Little Plover Study - Needs
 - Background material on the hydrogeologic and hydrometeorological setting.
 - Background material on the assessment that the Little Plover is oversubscribed - also introduces the major stakeholder groups.
 - Background material for students to read to be able to humanize a range of water users to understand their relationship with groundwater and how they value it - can be more general than the Little Plover.
 - Links to references on how groundwater value can be defined for different stakeholders and specific information on the value of water to farmers (for different crops, as needed), the fish vs flow curve, and the cost of pumping.
 - Links to resources introducing fairness, equity, or other value measures - ideally as they relate to groundwater, but more general references can also be useful.
 - Access to the MODFLOW input files so that they can 'read' the model and assess how difficult it might be to modify the inputs to conduct their analyses.
 - The MODFLOW model set up so that it can be run as it exists and so that it can be used to examine the suitability of superposition, and so that it can be used to calculate the capture fraction of one well.    
 - The analytical solution(s) - key references and the Jupyter Notebook to implement it.
 - Guidance on how to compare the numerical and analytical solutions for capture fraction of one well and interference of two wells (to assess the validity of superposition).
 - The Pareto optimal code that shows the Pareto front and dominated solutions (as an option)
   

 





