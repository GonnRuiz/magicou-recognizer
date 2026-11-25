# Attribution and data rights

## Geometry components

Generic geometry and rectification helpers in `arcana/vision/` are adapted from [Pokeum](https://github.com/TBLgGamin/pokeum), copyright 2026 TBLgGamin, under MIT. Its original copyright notice and terms remain in [LICENSE](LICENSE). Recognition, catalogue, indexing and API additions for this project are also distributed under MIT.

## Models and libraries

The encoder is generic [DINOv2-small](https://huggingface.co/facebook/dinov2-small), Apache-2.0, using a [pinned ONNX conversion](https://huggingface.co/Xenova/dinov2-small). Weights are downloaded separately with a SHA-256 check. The upstream license is preserved in [DINOV2_LICENSE.txt](arcana/assets/DINOV2_LICENSE.txt) and portable exports.

Optional [RapidOCR](https://github.com/RapidAI/RapidOCR) and OpenCV retain their own Apache-2.0 licensing. Other dependencies retain their respective licenses.

## Card data and images

Magic: The Gathering, card names, rules text, trademarks and artwork belong to Wizards of the Coast and their respective rights holders. Scryfall supplies metadata, images and prices subject to its terms and those rights. They are **not** relicensed under this repository's MIT license.

Reference JPEGs are not included in the repository. A code license does not grant permission to redistribute artwork or source datasets. Index/model artifacts have separate provenance and licensing considerations.

## Evaluation photographs

The optional physical-photo evaluation downloads three published examples from [CollectorVision](https://github.com/HanClinto/CollectorVision/tree/main/examples/images). They stay in the ignored local data directory and are not redistributed here. Using those photographs for evaluation does not incorporate that project's recognition implementation.

This is an unofficial independent project without affiliation with or endorsement by Wizards of the Coast or Scryfall.
