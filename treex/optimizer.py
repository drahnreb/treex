import functools
import inspect
import typing as tp

import jax
import jax.numpy as jnp
import optax

from treex import types
from treex.tree_object import TreeObject, annotation_map, module_update

O = tp.TypeVar("O", bound="Optimizer")
A = tp.TypeVar("A", bound="tp.Any")


class Optimizer(TreeObject):
    """Wraps an optax optimizer and turn it into a Pytree while maintaining a similar API.

    The main difference with optax is that tx.Optimizer contains its own state, thus, there is
    no `opt_state`.

    Example:
    ```python
    def main():
        ...
        optimizer = tx.Optimizer(optax.adam(1e-3))
        optimizer = optimizer.init(params)
        ...

    jax.jit
    def train_step(model, x, y, optimizer):
        ...
        params = optimizer.update(grads, params)
        ...
        return model, loss, optimizer
    ```

    Notice that since the optimizer is a `Pytree` it can naturally pass through `jit`.

    ### Differences with Optax
    * `init` return a new optimizer instance, there is no `opt_state`.
    * `update` doesn't get `opt_state` as an argument, instead it performs updates
        to its internal state inplace.
    * `update` applies the updates to the params and returns them by default, use `apply_updates=False` to
        to get the param updates instead.
    """

    opt_state: types.OptState[tp.Any, None]
    optimizer: optax.GradientTransformation

    _initialized: bool = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    def __init__(self, optimizer: optax.GradientTransformation):
        """
        Arguments:
            optimizer: An optax optimizer.
        """
        super().__init__()
        self.opt_state = None
        self.optimizer = optimizer

    def init(self: O, params: tp.Any) -> O:
        """
        Initialize the optimizer from an initial set of parameters.

        Arguments:
            params: An initial set of parameters.

        Returns:
            A new optimizer instance.
        """
        module = self.copy()
        params = annotation_map(lambda _: types.OptState, params)
        module.opt_state = module.optimizer.init(params)
        module._initialized = True
        return module

    # NOTE: current strategy is to convert annotation to `OptState`, this involves
    # 2 `annotation_map`s + a `module_update` but prints/tabulates preserve TreeObject information.
    # An alternative would be to flatten the params and use 2 `jax.tree_flatten` + a `jax.tree_unflatten`
    # which might be faster but prints/tabulates only show a flat list of params with no structure.
    def apply_updates(
        self, grads: A, params: tp.Optional[A] = None, return_updates: bool = False
    ) -> A:
        """
        Applies the parameters updates and updates the optimizers internal state inplace.

        Arguments:
            grads: the gradients to perform the update.
            params: the parameters to update. If `None` then `apply_updates` has to be `False`.
            return_updates: if `True` then the updates are returned instead of being applied.

        Returns:
            The updated parameters. Iftree_leaves `return_updates` is `True` then the updates are returned instead.
        """
        assert self.opt_state is not None
        if not return_updates and params is None:
            raise ValueError("params must be provided if updates are being applied")

        opt_grads = annotation_map(lambda _: types.OptState, grads)
        opt_params = annotation_map(lambda _: types.OptState, params)

        param_updates: A
        param_updates, self.opt_state = self.optimizer.update(
            opt_grads,
            self.opt_state,
            opt_params,
        )

        output: A
        if return_updates:
            output = param_updates
        else:
            output = optax.apply_updates(opt_params, param_updates)

        return module_update(grads, output)

    # THE FOLOWING METHODS ARE AUTOMATICALLY GENERATED
    # >>> DO NOT MODIFY <<<
    # run `python -m treex.optimizer` to update methods
    # --------------------------------------------------------------------------
    # <<<CODEGEN START>>>

    # <<<CODEGEN END>>>
    # --------------------------------------------------------------------------


# create a decorator to copy signatures
def _copy_signatue(source_fct):
    def _copy(target_fct):
        target_fct.__signature__ = inspect.signature(source_fct)
        return target_fct

    return _copy


def _create_wrapper(optax_optimizer: tp.Callable):
    name = optax_optimizer.__name__

    @_copy_signatue(optax_optimizer)
    @functools.wraps(optax_optimizer)
    def __init__(self: Optimizer, *args, **kwargs):
        self.optimizer = optax_optimizer(*args, **kwargs)

    __init__.__doc__ = optax_optimizer.__doc__

    return type(name, (Optimizer,), dict(__init__=__init__))


def _all_gradient_transformation():
    _gradient_transformation = {}
    for name, obj in inspect.getmembers(optax):
        if inspect.isfunction(obj):
            signature = inspect.signature(obj)

            # get return type
            ret_type = signature.return_annotation

            # add if return type is optax.GradientTransformation
            if ret_type == optax.GradientTransformation:
                _gradient_transformation[name] = (obj, signature)

    return _gradient_transformation


if __name__ == "__main__":
    import re
    from pathlib import Path

    gen_lines = []

    for i, (name, (obj, signature)) in enumerate(
        _all_gradient_transformation().items()
    ):
        signature: inspect.Signature
        signature_str = (
            str(signature)
            .replace("jax._src.numpy.lax_numpy", "jnp")
            .replace("typing.", "tp.")
            .replace("NoneType", "None")
            .replace("<class '", "")
            .replace("'>", "")
            .replace("ArrayTree", "chex.ArrayTree")
            .replace("optax._src.base", "optax")
        ).split(" -> ")[0]
        if "ForwardRef" in signature_str:
            signature_str = re.sub(
                r"ForwardRef\((.*?)\)", lambda m: m[1], signature_str
            )

        for type_name, type_obj in inspect.getmembers(tp):
            signature_str = re.sub(
                r"\b{type_name}\b".format(type_name=type_name),
                f"tp.{type_name}",
                signature_str,
            )

        signature_assigment_str = ", ".join(
            f"*{field}"
            if signature.parameters[field].kind == inspect.Parameter.VAR_POSITIONAL
            else f"**{field}"
            if signature.parameters[field].kind == inspect.Parameter.VAR_KEYWORD
            else f"{field}={field}"
            for field in signature.parameters
        )

        def _correct_doc(doc):
            return doc.replace("\n", "\n      ")

        gen_lines.extend(
            f'''\n
    @staticmethod
    def {name}{signature_str} -> "Optimizer":
        r"""{_correct_doc(obj.__doc__)}
        """
        return Optimizer(optax.{name}({signature_assigment_str}))
        '''.splitlines()
        )

    filepath = Path(__file__)
    lines = filepath.read_text().splitlines()

    idx_start = -1
    idx_end = -1

    for idx, line in enumerate(lines):
        if "<<<CODEGEN START>>>" in line and idx_start == -1:
            idx_start = idx
        elif "<<<CODEGEN END>>>" in line and idx_end == -1:
            idx_end = idx

    if idx_start < 0 or idx_end < 0:
        raise RuntimeError("Cannot find codegen start/end")

    new_lines = lines[: idx_start + 1] + gen_lines + lines[idx_end:]

    gen_text = "\n".join(new_lines)

    print(gen_text)
    filepath.write_text(gen_text)
