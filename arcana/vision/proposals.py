"""Multiple bounded hypotheses for occluded/black-bordered Magic cards.

Geometric proposals never assert identity: visual retrieval and RANSAC must
validate them. Guided captures prioritize the guide, not an internal text box.
"""
import cv2
import numpy as np

from .geometry import order_corners, polygon_area, aspect_ratio
from .imaging import cap_long_side
from .rectify import rectify, crop_guided_card, center_crop_to_card


def card_views(image, guided=False):
    if guided:
        yield crop_guided_card(image, .12)
    working = cap_long_side(image, 800)
    h, w = working.shape[:2]
    scale = image.shape[1] / w
    gray = cv2.cvtColor(working, cv2.COLOR_RGB2GRAY)
    masks = [cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 40, 120)]
    masks += [cv2.threshold(gray, level, 255, cv2.THRESH_BINARY_INV)[1] for level in (35, 65, 100)]
    proposals = []
    artworks = []
    for mask in masks:
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:80]:
            hull = cv2.convexHull(contour)
            area = cv2.contourArea(hull)
            if not .015 < area / (h * w) < .78:
                continue
            variants = [cv2.boxPoints(cv2.minAreaRect(hull))]
            for epsilon in (.015, .03, .06):
                approx = cv2.approxPolyDP(hull, epsilon * cv2.arcLength(hull, True), True)
                if len(approx) == 4:
                    variants.insert(0, approx.reshape(4, 2).astype(np.float32))
            for quad in variants:
                # An intact landscape art window can recover the outer card
                # even when a finger hides a corner/name. Geometry alone is
                # insufficient: the recognizer still verifies the reference.
                center = quad.mean(axis=0)
                clockwise = quad[np.argsort(np.arctan2(quad[:, 1]-center[1], quad[:, 0]-center[0]))]
                landscape = np.roll(clockwise, -int(np.argmin(clockwise.sum(axis=1))), axis=0)
                lengths = np.linalg.norm(np.roll(landscape, -1, axis=0)-landscape, axis=1)
                ratio = (lengths[0]+lengths[2]) / max(lengths[1]+lengths[3], 1)
                if 1.3 < ratio < 2 and area / (h*w) < .3:
                    art = np.array([[.07, .13], [.93, .13], [.93, .54], [.07, .54]], np.float32)
                    transform = cv2.getPerspectiveTransform(art, landscape.astype(np.float32))
                    outer = cv2.perspectiveTransform(np.array([[[0., 0.], [1., 0.], [1., 1.], [0., 1.]]], np.float32), transform)[0]
                    if not any(float(np.mean(np.linalg.norm(outer-old, axis=1))) < 12 for _, old in artworks):
                        artworks.append((area, outer))
                if area / (h*w) < .045:
                    continue
                quad = order_corners(quad)
                if not .48 < aspect_ratio(quad) < .95:
                    continue
                if np.any(quad[:, 0] < -w * .05) or np.any(quad[:, 1] < -h * .05):
                    continue
                # Ignore near-duplicate outlines, not genuinely different crops.
                if any(float(np.mean(np.linalg.norm(quad - old, axis=1))) < 12 for _, old in proposals):
                    continue
                proposals.append((polygon_area(quad), quad))
    for _, quad in sorted(artworks, key=lambda value: value[0], reverse=True)[:6]:
        yield rectify(image, quad * scale)
    for _, quad in sorted(proposals, key=lambda value: value[0], reverse=True)[:6]:
        yield rectify(image, quad * scale)
    yield center_crop_to_card(image)
