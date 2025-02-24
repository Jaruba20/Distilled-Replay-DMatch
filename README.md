# Distilled Replay with Distribution Matching


<div style="display: grid; grid-template-columns: repeat(8, 1fr); gap: 10px; justify-content: center; align-items: center;">
  <img src="miscellanea/distilled_figures/cifar10/orig_avion.png" width="150">
  <img src="miscellanea/distilled_figures/cifar10/orig_bird.png" width="150">
  <img src="miscellanea/distilled_figures/cifar10/orig_cat.png" width="150">
  <img src="miscellanea/distilled_figures/cifar10/orig_coche.png" width="150">
  <img src="miscellanea/distilled_figures/cifar10/orig_deer.png" width="150">
  <img src="miscellanea/distilled_figures/cifar10/orig_dog.png" width="150">
  <img src="miscellanea/distilled_figures/cifar10/orig_frog.png" width="150">
  <img src="miscellanea/distilled_figures/cifar10/orig_horse.png" width="150">
  <img src="miscellanea/distilled_figures/cifar10/dis_avion.png" width="150">
  <img src="miscellanea/distilled_figures/cifar10/dis_bird.png" width="150">
  <img src="miscellanea/distilled_figures/cifar10/dis_cat.png" width="150">
  <img src="miscellanea/distilled_figures/cifar10/dis_coche.png" width="150">
  <img src="miscellanea/distilled_figures/cifar10/dis_deer.png" width="150">
  <img src="miscellanea/distilled_figures/cifar10/dis_dog.png" width="150">
  <img src="miscellanea/distilled_figures/cifar10/dis_frog.png" width="150">
  <img src="miscellanea/distilled_figures/cifar10/dis_horse.png" width="150">
</div>


<br>

Code used for the experiments conducted on the paper [Continual Learning: Comparison and New Strategies Based on Dataset Distillation](https://github.com/Jaruba20/Distilled-Replay-DMatch/CLComparisonandNewStratsbasedonDD.pdf)


The model, scifar10_exp and sminst_exp folders are a modified version of the Distilled Replay implementation available at https://github.com/andrearosasco/DistilledReplay
of the paper https://arxiv.org/pdf/2103.15851.

The modified approach, achieves **equal** (SplitMNIST) or **better** (SplitCIFAR10) average accuracies than the original method while **reducing computing time in almost 50%**. 


<style>
  .image-grid {
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    gap: 10px;
    justify-content: center;
    align-items: center;
  }
  .image-grid img {
    width: 100px;
    height: auto;
  }
</style>

<div class="image-grid">
  <img src="miscellanea/distilled_figures/mnist/orig_0.png">
  <img src="miscellanea/distilled_figures/mnist/orig_1.png">
  <img src="miscellanea/distilled_figures/mnist/orig_2.png">
  <img src="miscellanea/distilled_figures/mnist/orig_3.png">
  <img src="miscellanea/distilled_figures/mnist/orig_4.png">
  <img src="miscellanea/distilled_figures/mnist/orig_5.png">
  <img src="miscellanea/distilled_figures/mnist/orig_6.png">
  <img src="miscellanea/distilled_figures/mnist/orig_7.png">
  <img src="miscellanea/distilled_figures/mnist/syn_0.png">
  <img src="miscellanea/distilled_figures/mnist/syn_1.png">
  <img src="miscellanea/distilled_figures/mnist/syn_2.png">
  <img src="miscellanea/distilled_figures/mnist/syn_3.png">
  <img src="miscellanea/distilled_figures/mnist/syn_4.png">
  <img src="miscellanea/distilled_figures/mnist/syn_5.png">
  <img src="miscellanea/distilled_figures/mnist/syn_6.png">
  <img src="miscellanea/distilled_figures/mnist/syn_7.png">
</div>

