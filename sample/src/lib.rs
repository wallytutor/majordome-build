#![deny(clippy::unwrap_used)]
#![deny(clippy::expect_used)]
#![deny(clippy::panic)]
#![deny(unused_must_use)]
#![deny(warnings)]

use pyo3::prelude::*;

pub mod prelude;

#[pymodule(name = "sample")]
pub mod sample {
    /// Mathematical constant π (pi).
    #[pymodule_export]
    pub const PI: f64 = std::f64::consts::PI;
}
