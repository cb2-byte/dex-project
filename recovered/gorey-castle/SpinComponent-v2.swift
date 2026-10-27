//
//  SpinComponent.swift
//  gorey castle
//
//  Created by Colin Brennan on 15/06/2026.
//

import RealityKit

/// A component that spins the entity around a given axis.
struct SpinComponent: Component {
    let spinAxis: SIMD3<Float> = [0, 1, 0]
}
